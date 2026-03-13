import re

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
        self.ui_init()
        self.info_set_task(self.tr('Daily Task'))
        self.ensure_main(time_out=180)
        
        # 1. 快照捕獲 (傳送前)
        self.open_daily(snapshot=True)
        
        # 2. 啟動深塔傳送 (非阻塞啟動)
        # 此處 book_opened=True 是因為剛才 open_daily 已經幫我們快速點擊了分頁
        self.go_to_tower(book_opened=True, wait=False)
        
        # 3. 核心優化：在點擊傳送後的黑屏加載間隙，並行分析快照
        used_stamina, completed = self.analyze_daily_snapshot()
        
        # 4. 現在才等待傳送加載完成
        self.wait_in_team_and_world(time_out=120)
        self.wait_until(lambda: self.in_team()[0], time_out=5, settle_time=0.1)

        condition1 = self.config.get('Auto Farm all Nightmare Nest')
        condition2 = self.config.get('Farm Nightmare Nest for Daily Echo')
        if condition1 or condition2:
            try:
                if condition1:
                    self.log_debug('Auto Farm all Nightmare Nest')
                    self.run_task_by_class(NightmareNestTask)
                elif condition2 and self.config.get('Which to Farm', self.support_tasks[0]) != self.support_tasks[0]:
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
            self.claim_daily()

        # 任務完成後，或判定已全領取：此時才關閉書本回到大世界
        self.back(after_sleep=0.1)
        self.wait_until(lambda: self.in_team_and_world(), time_out=5, settle_time=0.1)

        self.claim_mail()
        self.claim_battle_pass()
        self.log_info('Task completed', notify=True)

    def go_to_tower(self, book_opened=False, wait=True):
        self.info_set_task('Teleport to Tower of Adversity')
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
            pre_action=lambda: self.click_proceed_with_stamina(btn),
            time_out=5, settle_time=0.1
        )

        self.wait_click_travel()
        
        if wait:
            self.sleep(0.2)
            self.wait_in_team_and_world(time_out=120)
            self.wait_until(lambda: self.in_team()[0], time_out=5, settle_time=0.1)

    def claim_battle_pass(self):
        self.info_set_task('battle pass')
        self.send_key_down('alt')
        self.sleep(0.1)
        self.click_relative(0.86, 0.05, down_time=0.05)
        self.sleep(0.05)
        self.send_key_up('alt')
        if not self.wait_ocr(0.12, 0.13, 0.35, 0.25, match=re.compile(r'\d+'), settle_time=0.1, time_out=6, raise_if_not_found=False):
            self.log_error('can not battle pass, maybe ended')
        else:
            self.click(0.04, 0.3, after_sleep=0.1)
            self.wait_ocr(0.1, 0.1, 0.4, 0.3, match=re.compile(r'\d+'),
                          post_action=lambda: self.click(0.68, 0.91, after_sleep=0.1), settle_time=0.1, time_out=3,
                          raise_if_not_found=False)
            self.click(0.04, 0.17, after_sleep=0.1)
            self.wait_ocr(0.1, 0.1, 0.4, 0.3, match=re.compile(r'\d+'),
                          post_action=lambda: self.click(0.68, 0.91, after_sleep=0.1), settle_time=0.1, time_out=3,
                          raise_if_not_found=False)
        self.ensure_main()

    def open_daily(self, snapshot=False):
        self.log_info('open_daily')
        gray_book_quest = self.openF2Book(Labels.gray_book_quest)
        if not gray_book_quest:
            self.log_error(self.tr('open_daily can not find gray_book_quest'))
            return
            
        if snapshot:
            # 極速連拍模式：不再等待 OCR，利用 UI 響應間隙完成動作
            self._daily_snapshot1 = self.frame.copy()
            # 點擊卷軸區域下滑
            self.click(0.961, 0.6, after_sleep=0.05) 
            # 任務完成：壓縮切換分頁動作到快照流程中（提前為 go_to_tower 做準備）
            # 點擊「周期挑戰」分頁按鈕區域
            self.click_relative(0.04, 0.42, after_sleep=0.05) 
            self._daily_snapshot2 = self.frame.copy()
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
        self.info_set(self.tr('Consumed Waveplate'), current)
        return current, self.get_total_daily_points() >= 100

    def analyze_daily_snapshot(self):
        """
        分析由 open_daily(snapshot=True) 留下的截圖
        """
        if not hasattr(self, '_daily_snapshot1') or not hasattr(self, '_daily_snapshot2'):
            self.log_warning('No daily snapshots found, falling back to synchronous reading')
            return self.open_daily()
            
        self.info_set_task('Analyzing daily snapshots in background...')
        
        # 從第一張圖嘗試讀取
        progress = self.ocr(0.1, 0.1, 0.5, 0.75, match=re.compile(r'(\d+)/180'), frame=self._daily_snapshot1)
        if not progress:
            # 第一張圖沒讀到，從第二張圖讀取
            progress = self.ocr(0.1, 0.1, 0.5, 0.75, match=re.compile(r'(\d+)/180'), frame=self._daily_snapshot2)
            
        if progress:
            current = int(progress[0].name.split('/')[0])
        else:
            current = 0
            
        # 讀取活躍度點數 (通常在第一或第二頁都有進度條)
        points_boxes = self.ocr(0.19, 0.8, 0.30, 0.93, match=number_re, frame=self._daily_snapshot1)
        if not points_boxes:
            points_boxes = self.ocr(0.19, 0.8, 0.30, 0.93, match=number_re, frame=self._daily_snapshot2)
            
        points = int(points_boxes[0].name) if points_boxes else 0
        self.info_set(self.tr('Activity Pts'), points)

        # 體力也是異步讀取 (現在在活躍度之後設置，以符合用戶要求的順序)
        self.get_stamina(frame=self._daily_snapshot1)
        self.info_set(self.tr('Consumed Waveplate'), current)
        
        # 清理截圖釋放內存
        del self._daily_snapshot1
        del self._daily_snapshot2
        
        return current, points >= 100

    def get_total_daily_points(self):
        points_boxes = self.ocr(0.19, 0.8, 0.30, 0.93, match=number_re)
        if points_boxes:
            points = int(points_boxes[0].name)
        else:
            points = 0
        self.info_set(self.tr('Activity Pts'), points)
        return points

    def claim_daily(self):
        self.info_set_task('claim daily')
        self.ensure_main(time_out=5)
        self.open_daily()

        # 回歸上游邏輯：單次點擊領取全部，不重試（避免連點跳轉）
        self.click(0.87, 0.17, after_sleep=0.5)
        self.sleep(1)

        total_points = self.get_total_daily_points()
        # 直接更新 Activity Pts 即可，無需重複鍵名
        self.info_set(self.tr('Activity Pts'), total_points)
        if total_points < 100:
            raise Exception("Can't complete daily task, may need to increase stamina manually!")

        self.click(0.89, 0.85, after_sleep=0.5)
        self.ensure_main(time_out=10)

    def claim_mail(self):
        self.info_set_task('claim mail')
        self.ensure_main(time_out=5) # 確保在選單中，會執行 Esc 動作
        self.click(0.64, 0.95, after_sleep=1)
        self.click(0.14, 0.9, after_sleep=1)
        self.ensure_main(time_out=10)
