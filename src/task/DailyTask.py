import re
import os

from qfluentwidgets import FluentIcon

from ok import Logger, TaskDisabledException
from src.Labels import Labels
from src.task.BaseWWTask import number_re, stamina_re
from src.task.FarmEchoTask import FarmEchoTask
from src.task.ForgeryTask import ForgeryTask
from src.task.NightmareNestTask import NightmareNestTask
from src.task.TacetTask import TacetTask
from src.task.SimulationTask import SimulationTask
from src.task.WWOneTimeTask import WWOneTimeTask
from src.task.BaseCombatTask import BaseCombatTask

logger = Logger.get_logger(__name__)


class DailyTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Daily Task"
        self.group_name = "Daily"
        self.group_icon = FluentIcon.CALENDAR
        self.icon = FluentIcon.CAR
        self.support_schedule_task = True
        self.support_tasks = ["Tacet Suppression", "Forgery Challenge", "Simulation Challenge"]
        self.default_config = {
            'Which to Farm': self.support_tasks[0],
            'Which Tacet Suppression to Farm': 1,  # starts with 1
            'Which Forgery Challenge to Farm': 1,  # starts with 1
            'Material Selection': 'Shell Credit',
            'Auto Farm all Nightmare Nest': False,
            'Farm Nightmare Nest for Daily Echo': True,
        }
        self.config_description = {
            'Which Tacet Suppression to Farm': 'The Tacet Suppression number in the F2 list.',
            'Which Forgery Challenge to Farm': 'The Forgery Challenge number in the F2 list.',
            'Material Selection': 'Resonator EXP / Weapon EXP / Shell Credit',
            'Farm Nightmare Nest for Daily Echo': 'Farm 1 Echo from Nightmare Nest to complete Daily Task when needed.'
        }
        material_option_list = ['Resonator EXP', 'Weapon EXP', 'Shell Credit']
        self.config_type = {
            'Which to Farm': {
                'type': "drop_down",
                'options': self.support_tasks
            },
            'Material Selection': {
                'type': 'drop_down',
                'options': material_option_list
            },
        }
        self.description = "Login, claim monthly card, farm echo, and claim daily reward"

    def pause(self):
        """
        防護暫停崩潰 Bug：當 executor.current_task 為 None 時點擊暫停會引發 Exception。
        此處強制校對狀態以確保暫停成功執行。
        """
        if self.executor.current_task is None:
            self.executor.current_task = self
        super().pause()

    def run(self):
        WWOneTimeTask.run(self)
        self.ensure_main(time_out=180)
        
        # 1. 快照捕獲 (傳送前)
        self.open_daily(snapshot=True)
        
        # 2. 啟動深塔傳送 (非阻塞啟動)
        # 此處 book_opened=True 是因為剛才 open_daily 已經幫我們快速點擊了分頁
        self.go_to_tower(book_opened=True, wait=False)
        
        # 3. 核心優化：在點擊傳送後的黑屏加載間隙，並行分析快照
        self.info_set('current task', self.tr('Analyzing daily snapshots in background...'))
        used_stamina, completed = self.analyze_daily_snapshot()
        
        # 4. 現在才等待傳送加載完成
        self.wait_in_team_and_world(time_out=120)
        self.wait_until(lambda: self.in_team()[0], time_out=5, settle_time=0.1)

        condition1 = self.config.get('Auto Farm all Nightmare Nest')
        condition2 = self.config.get('Farm Nightmare Nest for Daily Echo')
        if condition1 or condition2:
            try:
                if condition1:
                    self.info_set('current task', self.tr('Farming Nightmare Nest'))
                    self.log_debug('Auto Farm all Nightmare Nest')
                    self.run_task_by_class(NightmareNestTask)
                elif condition2 and self.config.get('Which to Farm', self.support_tasks[0]) != self.support_tasks[0]:
                    self.info_set('current task', self.tr('Farming Nightmare Nest for Daily Echo'))
                    self.log_debug('Farm Nightmare Nest for Daily Echo')
                    self.get_task_by_class(NightmareNestTask).run_capture_mode()
            except TaskDisabledException:
                raise
            except Exception as e:
                self.log_error("NightmareNestTask Failed", e)
                self.ensure_main(time_out=180)
        # used_stamina, completed = self.open_daily() # 已在 analyze_daily_snapshot 完成

        if not completed:
            if used_stamina < 180:
                target = self.config.get('Which to Farm', self.support_tasks[0])
                self.info_set('current task', self.tr(target))
                if target == self.support_tasks[0]:
                    self.get_task_by_class(TacetTask).farm_tacet(daily=True, used_stamina=used_stamina,
                                                                 config=self.config)
                elif target == self.support_tasks[1]:
                    self.get_task_by_class(ForgeryTask).farm_forgery(daily=True, used_stamina=used_stamina,
                                                                     config=self.config)
                else:
                    self.get_task_by_class(SimulationTask).farm_simulation(daily=True, used_stamina=used_stamina,
                                                                           config=self.config)
                self.ensure_main()
                self.sleep(1)
            self.log_info(self.tr('Claiming daily rewards'))
            self.claim_daily()

        # 確保回到大世界後再進入郵件與電台流程，避免重複按 ESC
        self.ensure_main(time_out=15)
        self.claim_mail()
        self.claim_battle_pass()
        self.log_info(self.tr('Daily one-stop completed'), notify=True)

    def go_to_tower(self, book_opened=False, wait=True):
        self.log_info(self.tr('Teleport to Tower of Adversity'))
        if not book_opened:
            self.ensure_main(time_out=80)
        gray_book_weekly = self.openF2Book(Labels.gray_book_weekly, opened=book_opened)
        if not gray_book_weekly:
            self.log_error(self.tr('go_to_tower can not find gray_book_weekly'))
            return
        
        # 點擊副本項
        self.click_box(gray_book_weekly, after_sleep=1)
        
        # 點擊前往
        btns = self.find_feature(Labels.boss_proceed, box=self.box_of_screen(0.94, 0.3, 0.97, 0.41), threshold=0.8)
        if btns is None:
            self.log_error(self.tr('go_to_tower can not find boss_proceed'))
            return
        btn = min(btns, key=lambda box: box.y)
        
        self.wait_until(
            lambda: not self.find_one(Labels.boss_proceed, box=self.box_of_screen(0.94, 0.3, 0.97, 0.41)),
            pre_action=lambda: self.click_proceed_with_stamina(btn, snapshot=False), # 禁止覆寫已有的精確快照
            time_out=5, settle_time=0.1
        )

        self.wait_click_travel()
        
        if wait:
            self.sleep(0.2)
            self.wait_in_team_and_world(time_out=120)
            self.log_info(self.tr('Arrived at Tower of Adversity'))
            self.wait_until(lambda: self.in_team()[0], time_out=5, settle_time=0.1)

    def claim_battle_pass(self):
        self.log_info(self.tr('Open Pioneers Podcast'))
        self.ensure_main(time_out=5)
        
        # 視覺變動檢測：開啟 Podcast 直到離開大世界狀態
        self.wait_until(
            lambda: not self.in_team_and_world(),
            pre_action=lambda: (
                self.send_key_down('alt'),
                self.click_relative(0.86, 0.05, down_time=0.05),
                self.send_key_up('alt'),
                self.sleep(0.5) # 增加緩衝給 UI 響應
            ),
            time_out=5, settle_time=0.8
        )

        if not self.wait_ocr(0.12, 0.13, 0.35, 0.25, match=re.compile(r'\d+'), settle_time=0.1, time_out=6, raise_if_not_found=False):
            self.log_error('can not battle pass, maybe ended')
        else:
            self.log_info(self.tr('Claim task reward'))
            # 視覺變動檢測：切換頁簽直到內容加載
            self.wait_until(
                lambda: self.ocr(0.1, 0.1, 0.4, 0.3, match=re.compile(r'\d+')),
                pre_action=lambda: self.click(0.04, 0.35, after_sleep=0.2),
                time_out=5, settle_time=0.2
            )
            # 領取按鈕 (不阻塞，因為後續有 ensure_main 處理彈窗)
            self.click(0.68, 0.91, after_sleep=0.5)

            self.log_info(self.tr('Claim season reward'))
            # 視覺變動檢測：切換頁簽直到內容加載
            self.wait_until(
                lambda: self.ocr(0.1, 0.1, 0.4, 0.3, match=re.compile(r'\d+')),
                pre_action=lambda: self.click(0.04, 0.17, after_sleep=0.2),
                time_out=5, settle_time=0.2
            )
            self.click(0.68, 0.91, after_sleep=0.5)
            
        self.ensure_main()

    def open_daily(self, snapshot=False):
        self.log_info('open_daily')
        gray_book_quest = self.openF2Book(Labels.gray_book_quest)
        if not gray_book_quest:
            self.log_error(self.tr('open_daily can not find gray_book_quest'))
            return
            
        if snapshot:
            # 確保初始位在第一個頁簽（活躍度），避免數據解析出錯
            self.click_relative(0.04, 0.16, after_sleep=0.4)
            # 極速三連拍模式：利用 UI 響應間隙快速獲取所有數據截圖
            # 1. 第一張：活躍度前半部分
            self._daily_snapshot1 = self.frame.copy()
            
            # 2. 模擬滾動並捕獲第二張：活躍度後半部分
            self.click(0.961, 0.6, after_sleep=0.04) 
            self._daily_snapshot2 = self.frame.copy()
            
            # 3. 切換至「周期挑戰」分頁並捕獲第三張：體力數據
            # 座標 0.04, 0.28 是側邊欄第二個按鈕區域
            self.click_relative(0.04, 0.28, after_sleep=0.2) 
            # 確保體力數據渲染完成後才截圖，避免背景分析為 -1
            self.wait_ocr(0.49, 0.0, 0.92, 0.10, match=stamina_re, time_out=2.5, raise_if_not_found=False)
            self._stamina_snapshot = self.frame.copy()
            
            # 保存快照以供用戶調試
            try:
                import cv2
                os.makedirs('logs/debug_snapshots', exist_ok=True)
                cv2.imwrite('logs/debug_snapshots/daily_1.png', self._daily_snapshot1)
                cv2.imwrite('logs/debug_snapshots/daily_2.png', self._daily_snapshot2)
                cv2.imwrite('logs/debug_snapshots/stamina_3.png', self._stamina_snapshot)
                self.log_info(self.tr('Snapshots saved to logs/debug_snapshots/ for debugging'))
            except Exception as e:
                self.log_error(f'Failed to save debug snapshots: {e}')
            return 
            
        # 脈衝點擊分頁直到 OCR 偵測到數字（取代 after_sleep=1.5 硬編碼）
        self.wait_until(
            lambda: self.ocr(0.1, 0.1, 0.5, 0.75, match=re.compile(r'\d+')),
            pre_action=lambda: self.click_box(gray_book_quest, after_sleep=0.3),
            time_out=5, settle_time=0.2, raise_if_not_found=False
        )
        # 嘗試匹配完整的體力進度格式
        progress = self.ocr(0.1, 0.1, 0.5, 0.75, match=re.compile(r'(\d+)/180'))
        if not progress:
            # 捲動翻頁，用 wait_until 取代 after_sleep=1 硬編碼
            self.wait_until(
                lambda: self.ocr(0.1, 0.1, 0.5, 0.75, match=re.compile(r'(\d+)/180')),
                pre_action=lambda: self.click(0.961, 0.6, after_sleep=0.3),
                time_out=5, settle_time=0.2, raise_if_not_found=False
            )
            progress = self.ocr(0.1, 0.1, 0.5, 0.75, match=re.compile(r'(\d+)/180'))
        if progress:
            current = int(progress[0].name.split('/')[0])
        else:
            current = 0
        self.get_stamina() # 同步讀取體力數據到看板
        self.info_set('Consumed Waveplate', current)
        return current, self.get_total_daily_points() >= 100

    def analyze_daily_snapshot(self):
        """
        異步分析：在傳送加載期間處理三張快照
        """
        if not hasattr(self, '_daily_snapshot1') or not hasattr(self, '_daily_snapshot2') or not hasattr(self, '_stamina_snapshot'):
            self.log_warning('Missing snapshots, falling back to synchronous reading')
            return self.open_daily()
            
        self.info_set('current task', self.tr('Analyzing snapshots in background...'))
        
        # 1. 體力分析 (使用第三張分頁截圖)
        # 背景分析結束後才統一更新 UI，減少中間過程的日誌冗餘
        current_stamina, backup_stamina, _ = self.get_stamina(frame=self._stamina_snapshot, update_info=True)
        
        # 2. 活躍度進度分析 (已消耗體力)
        # 移除 match 參數，手動解析以增加容錯
        progress_boxes = self.ocr(0.1, 0.1, 0.5, 0.75, frame=self._daily_snapshot1)
        if not progress_boxes:
            progress_boxes = self.ocr(0.1, 0.1, 0.5, 0.75, frame=self._daily_snapshot2)
            
        current = 0
        progress_re = re.compile(r'(\d+)/180')
        for box in progress_boxes:
            name = box.name.replace(' ', '')
            if match := progress_re.search(name):
                current = int(match.group(1))
                logger.info(f"Detected Consumed Waveplate: {current} from '{name}'")
                break
        self.info_set('Consumed Waveplate', current)
        
        # 3. 活躍度點數分析
        points_boxes = self.ocr(0.19, 0.8, 0.30, 0.93, frame=self._daily_snapshot1)
        points = 0
        for box in points_boxes:
            name = box.name.replace(' ', '')
            if match := re.compile(r'(\d+)').search(name):
                points = int(match.group(1))
                logger.info(f"Detected Activity Points: {points} from '{name}'")
                break
        self.info_set('Activity Pts', points)
        if points == 0:
            points_boxes = self.ocr(0.19, 0.8, 0.30, 0.93, frame=self._daily_snapshot2)
            for box in points_boxes:
                name = box.name.replace(' ', '')
                if match := re.compile(r'(\d+)').search(name):
                    points = int(match.group(1))
                    logger.info(f"Detected Activity Points (snapshot 2): {points} from '{name}'")
                    break
            self.info_set('Activity Pts', points)
        
        self.info_set('current task', self.tr('Analysis completed'))
        
        # 清理截圖
        del self._daily_snapshot1
        del self._daily_snapshot2
        del self._stamina_snapshot
        
        return current, points >= 100

    def get_total_daily_points(self):
        points_boxes = self.ocr(0.19, 0.8, 0.30, 0.93, match=number_re)
        if points_boxes:
            points = int(points_boxes[0].name)
        else:
            points = 0
        self.info_set('Activity Pts', points)
        return points

    def claim_daily(self):
        self.log_info(self.tr('Claiming daily rewards'))
        self.info_set('Log', self.tr('Claiming daily rewards'))
        self.open_daily()

        # 上游邏輯：快速點擊領取，不進行 Label 阻塞
        self.click(0.87, 0.17, after_sleep=0.5) 

        total_points = self.get_total_daily_points()
        self.info_set('Claimed Activity Pts', total_points)
        self.info_set('Log', f"{self.tr('Activity Pts')}: {total_points}")
        
        if total_points < 100:
            raise Exception("Can't complete daily task, may need to increase stamina manually!")

        # 領取寶箱
        self.click(0.89, 0.85, after_sleep=0.5)
        self.back(after_sleep=0.5)

    def claim_mail(self):
        self.info_set('current task', 'claim mail')
        self.info_set('Log', self.tr('Open ESC menu'))
        
        # 視覺變動檢測：開啟選單直到離開大世界狀態
        self.wait_until(
            lambda: not self.in_team_and_world(),
            pre_action=lambda: self.back(after_sleep=0.8), # 增加等待時間給動畫，避免二次脈衝關閉選單
            time_out=8, settle_time=1.0 # 降低重試頻率以防止 toggle 類按鍵重複觸發
        )
        
        self.log_info(self.tr('Open mail'))
        self.info_set('Log', self.tr('Open mail'))
        # 視覺變動檢測：點擊郵件直到頁面標題出現
        # 區域 0.0, 0.0, 0.2, 0.2 通常是標題區域
        self.wait_until(
            lambda: self.ocr(0.0, 0.0, 0.2, 0.2, match=re.compile(r'(郵件|Mail)')),
            pre_action=lambda: self.click(0.64, 0.95, after_sleep=0.5), # 座標 (0.64, 0.95)
            time_out=8, settle_time=0.5, raise_if_not_found=False
        )
        
        self.log_info(self.tr('Claim mail'))
        self.info_set('Log', self.tr('Claim mail'))
        # 點擊領取，此處點擊後會有較長的動畫與彈窗，使用較大的 sleep 確保穩定觸發，後續由 ensure_main 處理
        self.click(0.14, 0.9, after_sleep=1.5) 
        self.ensure_main(time_out=15)
