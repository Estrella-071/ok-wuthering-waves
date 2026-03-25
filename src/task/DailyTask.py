import os
import re
import signal
from concurrent.futures import ThreadPoolExecutor

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
            'After Task Complete': 'None',
        }
        self.config_description = {
            'Which Tacet Suppression to Farm': 'The Tacet Suppression number in the F2 list.',
            'Which Forgery Challenge to Farm': 'The Forgery Challenge number in the F2 list.',
            'Material Selection': 'Resonator EXP / Weapon EXP / Shell Credit',
            'Farm Nightmare Nest for Daily Echo': 'Farm 1 Echo from Nightmare Nest to complete Daily Task when needed.',
            'After Task Complete': 'Action after task: None / Close Game & Tool',
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
            'After Task Complete': {
                'type': 'drop_down',
                'options': ['None', 'Close Game & Tool']
            },
        }
        self.description = "Login, claim monthly card, farm echo, and claim daily reward"

    def run(self):
        # 运行状态重置
        self._daily_snapshot1 = None
        self._daily_snapshot2 = None
        self._stamina_snapshot = None
        self._activity_pts_achieved = False
        self._chests_claimed = False
        self._mail_claimed = False
        self._bp_claimed = False
        self._consumed_waveplate = 0
        self._is_book_open = False

        WWOneTimeTask.run(self)
        self.ensure_main(time_out=180)
        
        # 将子任务的 info_set/info_incr 重定向至 DailyTask，实现数据跨实例同步
        from src.task.NightmareNestTask import NightmareNestTask
        from src.task.TacetTask import TacetTask
        from src.task.ForgeryTask import ForgeryTask
        from src.task.SimulationTask import SimulationTask
        sub_tasks = [NightmareNestTask, TacetTask, ForgeryTask, SimulationTask]
        for task_class in sub_tasks:
            instance = self.get_task_by_class(task_class)
            # 設定代理 task，由 BaseWWTask 中覆寫的 info_set/info_incr 攔截分發，並且共用 info 字典
            instance._proxy_task = self
            instance.__dict__['info'] = self.info

        # 1. 初始分析
        result = self.open_daily(snapshot=True)
        self._is_book_open = True
        used_stamina, completed = result if result else (0, False)
        
        self.analyze_daily_snapshot()
        
        # 更新状态确保决策使用的是最新分析结果
        completed = self._activity_pts_achieved
        used_stamina = self._consumed_waveplate
        
        # 2. 执行刷取任务 (大世界/副本)
        if not completed:
            target = self.config.get('Which to Farm', self.support_tasks[0])
            condition1 = self.config.get('Auto Farm all Nightmare Nest')
            condition2 = self.config.get('Farm Nightmare Nest for Daily Echo')
            # 只有当不刷取无音区时，才利用梦魇巢穴补位日常
            if condition1 or (condition2 and target != self.support_tasks[0]):
                try:
                    if condition1:
                        self.info_set('current task', self.tr('Farming Nightmare Nest'))
                        self.info_set('Log', self.tr('Farming Nightmare Nest'))
                        self.run_task_by_class(NightmareNestTask)
                    elif condition2:
                        self.info_set('Log', self.tr('Farm Nightmare Nest for Daily Echo'))
                        self.get_task_by_class(NightmareNestTask).run_capture_mode()
                except TaskDisabledException:
                    raise
                except Exception as e:
                    # 如果是框架抛出的中断异常 (如 TaskStopException, TaskDisabledException)，则不执行耗时清理，直接向上抛出
                    if type(e).__name__ in ('TaskStopException', 'CancelledError', 'TaskDisabledException'):
                        raise e
                    logger.error(f"Error during Nightmare Nest: {e}")
                    self.ensure_main(time_out=180)
                    raise e

            used_stamina = self._consumed_waveplate
            if used_stamina < 180:
                target = self.config.get('Which to Farm', self.support_tasks[0])
                target_tr = self.tr(target)
                self.info_set('current task', target_tr)
                self.info_set('Log', self.tr('Start farming {}').format(target_tr))
                if target == self.support_tasks[0]:
                    self.get_task_by_class(TacetTask).farm_tacet(daily=True, used_stamina=used_stamina, config=self.config)
                elif target == self.support_tasks[1]:
                    self.get_task_by_class(ForgeryTask).farm_forgery(daily=True, used_stamina=used_stamina, config=self.config)
                else:
                    self.get_task_by_class(SimulationTask).farm_simulation(daily=True, used_stamina=used_stamina, config=self.config)

                self.ensure_main()
                self._is_book_open = False
                self.wait_in_team_and_world(time_out=5)  # 视觉等待替代固定 sleep(1)


        # 3. 大世界停泊 (根据当前实际状态传参)
        logger.info(f'Parking at Tower of Adversity (Book open: {self._is_book_open})')
        self.go_to_tower(book_opened=self._is_book_open, wait=True)

        # 4. 领取奖励与宝箱 (在停泊点执行)
        self.claim_daily(treasure_only=completed)

        # 5. 领取邮件
        self.claim_mail()

        # 6. 领取电台 (BP)
        self.claim_battle_pass()

        self.log_info(self.tr('Daily one-stop completed'), notify=True)
        
        # 7. 安全自动退出判断
        self._handle_auto_exit()

    def go_to_tower(self, book_opened=False, wait=True):
        self.log_info(self.tr('Teleport to Tower of Adversity'))
        self.info_set('Log', self.tr('Teleport to Tower of Adversity'))
        if not book_opened:
            self.ensure_main(time_out=80)
        
        gray_book_weekly = self.openF2Book(Labels.gray_book_weekly, opened=book_opened)
        if not gray_book_weekly:
            self.log_error('go_to_tower can not find gray_book_weekly')
            return
        
        self.click_box(gray_book_weekly, after_sleep=1)
        
        # 寻找并点击「前往」按钮 (对齐 upstream 的稳定区域)
        btn = self.find_one(Labels.boss_proceed, box=self.box_of_screen(0.94, 0.3, 0.97, 0.41), threshold=0.8)
        if btn is None:
            # 扩大搜索范围再试一次 (兜底)
            btn = self.find_one(Labels.boss_proceed, box=self.box_of_screen(0.94, 0.25, 0.98, 0.5), threshold=0.7)
            
        if btn:
            self.click_box(btn, after_sleep=1)
        else:
            # 最后的坐标兜底
            logger.warning("boss_proceed visual failed, trying coordinate click")
            self.click_relative(0.88, 0.28, after_sleep=1)

        self.wait_click_travel()
        self.log_info(self.tr('Waiting for teleport to complete'))
        self.info_set('Log', self.tr('Waiting for teleport to complete'))
        self._is_book_open = False # Teleport confirmation closes the book

        if wait:
            self.sleep(0.2)
            self.wait_in_team_and_world(time_out=120)
            self.wait_until(lambda: self.in_team()[0], time_out=5, settle_time=0.1)

    def _open_pioneers_podcast(self):
        self.send_key_down('alt')
        self.sleep(0.1)
        self.click_relative(0.86, 0.05)
        self.sleep(0.05)
        self.send_key_up('alt')
        self.sleep(1)
        return not self.in_team_and_world()

    def claim_battle_pass(self):
        self.log_info(self.tr('Open Pioneers Podcast'))
        self.info_set('current task', self.tr('Pioneers Podcast'))
        self.info_set('Log', self.tr('Alt + Click to open Pioneers Podcast'))
        self.ensure_main(time_out=5)

        if not self.wait_until(self._open_pioneers_podcast,
                               time_out=10, raise_if_not_found=False):
            self.log_error('can not open battle pass')
            self.ensure_main(time_out=15)
            return

        # 1. 領取任務獎勵 (Task Rewards)
        # 循環重試切換到「任務」分頁 (座標 0.04, 0.35) 直到頁面數字出現
        self.log_info(self.tr('Switching to task rewards tab'))
        self.wait_until(
            lambda: self.ocr(0.1, 0.1, 0.4, 0.3, match=re.compile(r'\d+')),
            pre_action=lambda: self.click(0.04, 0.35, after_sleep=0.3),
            time_out=6, settle_time=0.2, raise_if_not_found=False
        )
        
        # 再次確認處於任務頁後執行「全部領取」 (右下角按鈕 0.68, 0.91)
        self.log_info(self.tr('Claiming task rewards'))
        self.click(0.68, 0.91, after_sleep=1.5) 
        self._handle_bp_modal()

        # 2. 領取賽季獎勵 (Season Rewards)
        self.log_info(self.tr('Switching to season rewards tab'))
        self.wait_until(
            lambda: self.ocr(0.1, 0.1, 0.4, 0.3, match=re.compile(r'\d+')),
            pre_action=lambda: self.click(0.04, 0.17, after_sleep=0.3),
            time_out=10, settle_time=0.4, raise_if_not_found=False
        )
        
        self.log_info(self.tr('Claiming season rewards'))
        self.click(0.68, 0.91, after_sleep=1.0)
        self._handle_bp_modal()
            
        self._bp_claimed = True
        self.ensure_main(time_out=15)

    def _handle_bp_modal(self):
        """處理領取獎勵後彈出的『獲得/決定』彈框 (支持多語系)"""
        if self.wait_until(
            lambda: self.ocr(0.4, 0.8, 0.8, 1.0, match=re.compile(r'(決定|確認|Confirm|Decision|OK|確定|確定|확인|受取|獲得)')),
            time_out=3, raise_if_not_found=False
        ):
            self.log_info(self.tr('BP modal detected, clicking Confirm/Decision button'))
            self.click(0.7, 0.91, after_sleep=1.0)


    def open_daily(self, snapshot=False, skip_ocr=False):
        self.log_info('open_daily')
        self.info_set('Log', self.tr('Open F2 book'))
        gray_book_quest = self.openF2Book(Labels.gray_book_quest)
        if not gray_book_quest:
            self.log_error(self.tr('open_daily can not find gray_book_quest'))
            return

        if skip_ocr:
            self.log_info("Skipping OCR as requested (Fast Mode)")
            self.click_relative(0.04, 0.16, after_sleep=0.4)
            return
            
        if snapshot:
            self.click_relative(0.04, 0.16, after_sleep=0.3)
            
            self._daily_snapshot1 = self.frame.copy()
            
            self.click(0.961, 0.6, after_sleep=0.2) 
            self._daily_snapshot2 = self.frame.copy()

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._extract_points, self._daily_snapshot1)
                self.click_relative(0.04, 0.28, after_sleep=0.2)
                try:
                    current_points = future.result(timeout=4)
                    completed = current_points >= 100
                    if completed:
                        logger.info(f"快速模式: 活跃度 {current_points} >= 100")
                        self.info_set('Activity Pts', f'{current_points}/100')
                    else:
                        logger.debug(f"活跃度 {current_points} < 100")
                except Exception as e:
                    self.log_error('Parallel OCR failed', e)
                    current_points = 0
                    completed = False

            self.wait_ocr(0.49, 0.0, 0.92, 0.10, match=stamina_re, time_out=2.5, raise_if_not_found=False)
            self._stamina_snapshot = self.frame.copy()
            
            if self.debug:
                os.makedirs('logs/debug_snapshots', exist_ok=True)
                import cv2
                cv2.imwrite('logs/debug_snapshots/daily_1.png', self._daily_snapshot1)
                cv2.imwrite('logs/debug_snapshots/daily_2.png', self._daily_snapshot2)
                cv2.imwrite('logs/debug_snapshots/stamina_3.png', self._stamina_snapshot)
                
            return current_points, completed
            
        self.info_set('Log', self.tr('Detecting stamina and activity points'))
        self.wait_until(
            lambda: self.ocr(0.1, 0.1, 0.5, 0.75, match=re.compile(r'\d+')),
            pre_action=lambda: self.click_box(gray_book_quest, after_sleep=0.1),
            time_out=3, settle_time=0.1, raise_if_not_found=False
        )
        # 尝试匹配完整的体力进度格式
        progress = self.ocr(0.1, 0.1, 0.5, 0.75, match=re.compile(r'(\d+)/180'))
        if not progress:
            self.wait_until(
                lambda: self.ocr(0.1, 0.1, 0.5, 0.75, match=re.compile(r'(\d+)/180')),
                pre_action=lambda: self.click(0.961, 0.6, after_sleep=0.1),
                time_out=3, settle_time=0.1, raise_if_not_found=False
            )
            progress = self.ocr(0.1, 0.1, 0.5, 0.75, match=re.compile(r'(\d+)/180'))
        if progress:
            current = int(progress[0].name.split('/')[0])
        else:
            current = 0
        self.get_stamina()
        self._consumed_waveplate = current
        self.info_set('Consumed Waveplate', f'{current}/180')
        return current, self.get_total_daily_points() >= 100

    def analyze_daily_snapshot(self):
        if not hasattr(self, '_daily_snapshot1') or not hasattr(self, '_daily_snapshot2') or not hasattr(self, '_stamina_snapshot'):
            return self.open_daily()

        self.info_set('Log', self.tr('Analyzing snapshots'))
        
        # 解析快照体力
        current_stamina, backup_stamina, _ = self.get_stamina(frame=self._stamina_snapshot, update_info=True)

        # 活跃度消耗
        progress_re = re.compile(r'(\d+)/180')
        
        def find_waveplate(frame):
            # 这里的 ROI 是书本右侧进度条区域
            boxes = self.ocr(0.1, 0.1, 0.5, 0.75, frame=frame)
            for box in (boxes or []):
                name = box.name.replace(' ', '')
                if match := progress_re.search(name):
                    return int(match.group(1))
            return None

        current = find_waveplate(self._daily_snapshot1)
        if current is None:
            current = find_waveplate(self._daily_snapshot2)
        
        current = current if current is not None else 0
        logger.info(f"Detected Consumed Waveplate: {current}")
        self._consumed_waveplate = current
        # 同时更新用于计算累计消耗的 key，确保后续子任务能拿到正确的初始基数
        self.info_set('Consumed Waveplate', f'{current}/180')

        # 活跃度数值
        points = self._extract_points(self._daily_snapshot1) or self._extract_points(self._daily_snapshot2)
        self.info_set('Activity Pts', f'{points}/100' if points else '0/100')
        if points >= 100:
            self._activity_pts_achieved = True

        self.info_set('current task', self.tr('Analysis completed'))
        self.info_set('Log', self.tr('Analysis completed'))

        del self._daily_snapshot1
        del self._daily_snapshot2
        del self._stamina_snapshot

        return current, points >= 100

    def _extract_points(self, frame):
        points_boxes = self.ocr(0.19, 0.8, 0.30, 0.93, frame=frame)
        for box in (points_boxes or []):
            name = box.name.replace(' ', '')
            if match := number_re.search(name):
                points = int(match.group(1))
                logger.debug(f"Detected Activity Points: {points}")
                return points
        return 0

    def get_total_daily_points(self):
        points_boxes = self.ocr(0.19, 0.8, 0.30, 0.93, match=number_re)
        if points_boxes:
            points = int(points_boxes[0].name)
        else:
            points = 0
        self.info_set('Activity Pts', f'{points}/100')
        return points

    def claim_daily(self, treasure_only=False):
        self.log_info(self.tr('Claiming daily rewards'))
        self.info_set('Log', self.tr('Claiming daily rewards'))
        # 强制使用快速模式，避免在领取时重新执行慢速 OCR
        self.open_daily(skip_ocr=True)

        if not treasure_only:
            # “全部领取”按钮
            self.click(0.87, 0.17, after_sleep=0.2) 
            total_points = self.get_total_daily_points()
            self.info_set('Claimed Activity Pts', f'{total_points}/100')
            self.info_set('Log', f"{self.tr('Activity Pts')}: {total_points}")
            if total_points >= 100:
                self._activity_pts_achieved = True
            else:
                self.log_warning(self.tr("Activity points not enough, attempting to claim chests anyway"))
        else:
            # 如果是 treasure_only，说明启动时就已经达到 100 点
            self._activity_pts_achieved = True

        # 使用 OCR 定位宝箱 (整合上游改进)
        self.click_daily_reward_box(100)
        self._chests_claimed = True

        self.ensure_main(time_out=10)

    def click_daily_reward_box(self, reward_points):
        reward_boxes = self.ocr(
            0.72, 0.78, 0.98, 0.98,
            match=re.compile(rf'^{reward_points}$')
        )
        if reward_boxes:
            reward_box = max(reward_boxes, key=lambda box: box.x)
            click_box = reward_box.copy(
                x_offset=int(-reward_box.width * 0.8),
                y_offset=int(-reward_box.height * 3.0),
                width_offset=int(reward_box.width * 1.6),
                height_offset=int(reward_box.height * 2.2),
                name=f'daily_reward_{reward_points}'
            )
            self.log_info(self.tr('claim daily reward {} via OCR').format(reward_points))
            self.click(click_box, after_sleep=1)
            return True

        # 座標兜底
        self.log_info(self.tr('claim daily reward {} via fallback coordinate').format(reward_points))
        self.click(0.94, 0.85, after_sleep=1)
        return False

    def claim_mail(self):
        self.log_info(self.tr('Claim mail'))
        self.info_set('current task', self.tr('Mail'))
        self.ensure_main(time_out=5)
        
        # 1. 直接進入 ESC 選單 (如果不在的話)
        if self.in_team_and_world():
            self.send_key('esc', after_sleep=0.8)
        
        # 2. 領取郵件
        self.log_info(self.tr('Opening mail and collecting all items'))
        
        # 這裡組合：點擊郵件座標 -> 等待左下角出現領取按鈕 (多語系) -> 點擊領取
        self.click(0.64, 0.95, after_sleep=0.5)
        
        if self.wait_until(
            lambda: self.ocr(0.0, 0.8, 0.4, 1.0, match=re.compile(r'(全部領取|全部领取|ClaimAll|一括受取|일괄수령|Collect|受取|모두)')),
            time_out=6, settle_time=0.1, raise_if_not_found=False
        ):
            self.log_info(self.tr('Collect All button detected, clicking'))
            self.click(0.12, 0.91, after_sleep=1.0)
        
        self.back(after_sleep=1.0)
        self._mail_claimed = True
        self.ensure_main(time_out=15)


    def _handle_auto_exit(self):
        action = self.config.get('After Task Complete', 'None')
        if action == 'None':
            return
        # 安全判定: 四项指标全部达标才允许退出
        if self._activity_pts_achieved and self._chests_claimed and self._mail_claimed and self._bp_claimed:
            logger.info(f"All conditions met, action: {action}")
            if action == 'Close Game & Tool':
                os.system('taskkill /f /im Client-Win64-Shipping.exe')
                logger.info("Game killed, exiting script")
                os.kill(os.getpid(), signal.SIGTERM)
        else:
            self.log_warning(f"Auto-exit not met: Pts={self._activity_pts_achieved}, Chests={self._chests_claimed}, Mail={self._mail_claimed}, BP={self._bp_claimed}")
