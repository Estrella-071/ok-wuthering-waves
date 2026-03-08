import re

from qfluentwidgets import FluentIcon

from ok import Logger
from src.task.BaseCombatTask import BaseCombatTask
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class DomainTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.teleport_timeout = 100
        self.stamina_once = 0
        self.group_name = "Dungeon"
        self.group_icon = FluentIcon.HOME

    def make_sure_in_world(self):
        if self.in_realm():
            self.send_key('esc', after_sleep=1)
            self.wait_click_feature('gray_confirm_exit_button', relative_x=-1, raise_if_not_found=False,
                                    time_out=3, click_after_delay=0.5, threshold=0.7)
            self.wait_in_team_and_world(time_out=self.teleport_timeout)
        else:
            self.ensure_main()

    def open_F2_book_and_get_stamina(self):
        gray_book_boss = self.openF2Book('gray_book_boss')
        self.click_box(gray_book_boss, after_sleep=1)
        return self.get_stamina()

    def farm_in_domain(self, must_use=0):
        if self.stamina_once <= 0:
            raise RuntimeError('"self.stamina_once" must be override')
        self.info_incr('used stamina', 0)
        
        from src.utils.ProgressFormatter import RunStatus
        import math
        total_rounds = 1
        if must_use > 0:
            total_rounds = math.ceil(must_use / self.stamina_once)
            
        round_count = 0
        while True:
            round_count += 1
            combat_node_id = f'combat_{round_count}'
            combat_detail_id = f'combat_detail_{round_count}'
            if hasattr(self, 'formatter') and self.formatter:
                round_str = f"戰鬥 {round_count}/{total_rounds}" if must_use > 0 else f"戰鬥 {round_count}"
                parent_id = 'farm' if self.formatter.get_node('farm') else 'root'
                if round_count == 1:
                    tp_node = self.formatter.get_node('tp')
                    if tp_node:
                        self.formatter.set_status('tp', RunStatus.DONE)

                self.formatter.add_node(combat_node_id, round_str, parent_id=parent_id)
                self.formatter.set_status(combat_node_id, RunStatus.RUNNING)
                self.formatter.add_node(combat_detail_id, '正在跑圖', parent_id=combat_node_id)
                self.formatter.set_status(combat_detail_id, RunStatus.RUNNING)

            self.walk_until_f(time_out=4, backward_time=0, raise_if_not_found=True)
            self.pick_f()

            if hasattr(self, 'formatter') and self.formatter:
                self.formatter.update_text(combat_detail_id, '戰鬥中')

            self.combat_once()
            self.sleep(3)

            if hasattr(self, 'formatter') and self.formatter:
                self.formatter.update_text(combat_detail_id, '前往領取獎勵')

            self.walk_to_treasure()
            self.pick_f(handle_claim=False)
            can_continue, used = self.use_stamina(once=self.stamina_once, must_use=must_use)
            self.info_incr('used stamina', used)
            must_use -= used
            self.sleep(4)

            if hasattr(self, 'formatter') and self.formatter:
                self.formatter.set_status(combat_detail_id, RunStatus.DONE)
                self.formatter.set_status(combat_node_id, RunStatus.DONE)
                
            if not can_continue:
                self.log_info("used all stamina")
                break
            self.click(0.68, 0.84, after_sleep=1)  # farm again
            if confirm := self.wait_feature(
                    ['confirm_btn_hcenter_vcenter', 'confirm_btn_highlight_hcenter_vcenter'],
                    raise_if_not_found=False,
                    threshold=0.6,
                    time_out=2):
                self.click(0.49, 0.55, after_sleep=0.5)  # 点击不再提醒
                self.click(confirm, after_sleep=0.5)
                self.wait_click_feature(
                    ['confirm_btn_hcenter_vcenter', 'confirm_btn_highlight_hcenter_vcenter'],
                    relative_x=-1, raise_if_not_found=False,
                    threshold=0.6,
                    time_out=1)
            self.wait_in_team_and_world(time_out=self.teleport_timeout)
            self.sleep(1)
        #
        self.click(0.42, 0.84, after_sleep=2)  # back to world
        self.make_sure_in_world()
