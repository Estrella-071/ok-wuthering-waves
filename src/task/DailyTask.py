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
from src.utils.ProgressFormatter import ProgressFormatter, RunStatus

logger = Logger.get_logger(__name__)


class DailyTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Daily Task"
        self.group_name = "Daily"
        self.group_icon = FluentIcon.CALENDAR
        self.icon = FluentIcon.CAR
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

    def run(self):
        self.formatter = ProgressFormatter('每日一條龍')
        self.formatter.add_node('login', '登入')
        self.formatter.add_node('monthly', '領取月卡')
        self.formatter.add_node('tower', '傳送至深塔')
        self.formatter.add_node('info', '確認資訊')
        self.formatter.add_node('info_active', '活躍度', 'info')
        self.formatter.add_node('info_stamina', '結晶玻片', 'info')
        self.formatter.add_node('farm', f"刷{self.config.get('Which to Farm', self.support_tasks[0])}")
        self.formatter.add_node('stamina_done', '結晶消耗完成')
        self.formatter.add_node('claim_active', '開始領取活躍度')
        self.formatter.add_node('claim_bp', '領取先約電台')

        WWOneTimeTask.run(self)
        self.formatter.set_status('login', RunStatus.RUNNING)
        self.ensure_main(time_out=180)
        self.formatter.set_status('login', RunStatus.DONE)
        
        self.formatter.set_status('tower', RunStatus.RUNNING)
        self.go_to_tower()
        self.formatter.set_status('tower', RunStatus.DONE)

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
        used_stamina, completed = self.open_daily()

        self.send_key('esc', after_sleep=1)
        self.formatter.set_status('farm', RunStatus.RUNNING)
        if not completed:
            if used_stamina < 180:
                target = self.config.get('Which to Farm', self.support_tasks[0])
                if target == self.support_tasks[0]:
                    task = self.get_task_by_class(TacetTask)
                    task.formatter = self.formatter
                    task.farm_tacet(daily=True, used_stamina=used_stamina, config=self.config)
                elif target == self.support_tasks[1]:
                    task = self.get_task_by_class(ForgeryTask)
                    task.formatter = self.formatter
                    task.farm_forgery(daily=True, used_stamina=used_stamina, config=self.config)
                else:
                    task = self.get_task_by_class(SimulationTask)
                    task.formatter = self.formatter
                    task.farm_simulation(daily=True, used_stamina=used_stamina, config=self.config)
                self.sleep(4)
            self.formatter.set_status('farm', RunStatus.DONE)
            self.formatter.set_status('stamina_done', RunStatus.DONE)

            self.formatter.set_status('claim_active', RunStatus.RUNNING)
            self.claim_daily()
            self.formatter.set_status('claim_active', RunStatus.DONE)

        self.claim_mail()
        self.sleep(1)
        self.formatter.set_status('claim_bp', RunStatus.RUNNING)
        self.claim_battle_pass()
        self.formatter.set_status('claim_bp', RunStatus.DONE)
        self.log_info('Task completed', notify=True)

    def go_to_tower(self):
        self.log_info('go to tower')
        self.ensure_main(time_out=80)
        gray_book_weekly = self.openF2Book(Labels.gray_book_weekly)
        if not gray_book_weekly:
            self.log_error('go_to_tower can not find gray_book_weekly')
            return
        self.click_box(gray_book_weekly, after_sleep=1)
        btn = self.find_one(Labels.boss_proceed, box=self.box_of_screen(0.94, 0.3, 0.97, 0.41), threshold=0.8)
        if btn is None:
            self.ensure_main(time_out=10)
            return
        self.click_box(btn, after_sleep=1)
        self.wait_click_travel()
        self.wait_in_team_and_world(time_out=120)
        self.sleep(1)

    def claim_battle_pass(self):
        self.log_info('battle pass')
        self.send_key_down('alt')
        self.sleep(0.05)
        self.click_relative(0.86, 0.05)
        self.send_key_up('alt')
        if not self.wait_ocr(0.2, 0.13, 0.32, 0.22, match=re.compile(r'\d+'), settle_time=1, raise_if_not_found=False):
            self.log_error('can not battle pass, maybe ended')
        else:
            self.click(0.04, 0.3, after_sleep=1)
            self.click(0.68, 0.91, after_sleep=3)
            self.click(0.04, 0.17, after_sleep=2)
            self.click(0.68, 0.91, after_sleep=2)
            self.wait_ocr(0.2, 0.13, 0.32, 0.22, match=re.compile(r'\d+'),
                          post_action=lambda: self.click(0.68, 0.91, after_sleep=1), settle_time=1,
                          raise_if_not_found=False)
        self.ensure_main()

    def open_daily(self):
        self.log_info('open_daily')
        gray_book_quest = self.openF2Book("gray_book_quest")
        self.click_box(gray_book_quest, after_sleep=1.5)
        progress = self.ocr(0.1, 0.1, 0.5, 0.75, match=re.compile(r'^(\d+)/180$'))
        if not progress:
            self.click(0.961, 0.6, after_sleep=1)
            progress = self.ocr(0.1, 0.1, 0.5, 0.75, match=re.compile(r'^(\d+)/180$'))
        if progress:
            current = int(progress[0].name.split('/')[0])
        else:
            current = 0
        self.info_set('current daily progress', current)
        if hasattr(self, 'formatter') and self.formatter:
            self.formatter.update_text('info_active', f"活躍度 {current} / 100")
            self.formatter.set_status('info_active', RunStatus.DONE)
        return current, self.get_total_daily_points() >= 100

    def get_total_daily_points(self):
        points_boxes = self.ocr(0.19, 0.8, 0.30, 0.93, match=number_re)
        if points_boxes:
            points = int(points_boxes[0].name)
        else:
            points = 0
        self.info_set('total daily points', points)
        return points

    def claim_daily(self):
        self.info_set('current task', 'claim daily')
        self.ensure_main(time_out=5)
        self.open_daily()

        self.click(0.87, 0.17, after_sleep=0.5)
        self.sleep(1)

        total_points = self.get_total_daily_points()
        self.info_set('daily points', total_points)
        if total_points < 100:
            raise Exception("Can't complete daily task, may need to increase stamina manually!")

        self.click(0.89, 0.85, after_sleep=1)
        self.ensure_main(time_out=10)

    def claim_mail(self):
        self.info_set('current task', 'claim mail')
        self.back(after_sleep=1.5)
        self.click(0.64, 0.95, after_sleep=1)
        self.click(0.14, 0.9, after_sleep=1)
        self.ensure_main(time_out=10)
