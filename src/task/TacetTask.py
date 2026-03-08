import math
import time

from qfluentwidgets import FluentIcon

from ok import Logger
from src.task.BaseCombatTask import BaseCombatTask
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class TacetTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = FluentIcon.FLAG
        self.group_name = "Dungeon"
        self.group_icon = FluentIcon.HOME
        self.description = "Farms the selected Tacet Suppression, until no stamina. Must be able to teleport (F2)."
        self.name = "Tacet Suppression"
        default_config = {
            'Which Tacet Suppression to Farm': 1,  # starts with 1
        }
        self.total_number = 16
        self.target_enemy_time_out = 10
        default_config.update(self.default_config)
        self.config_description = {
            'Which Tacet Suppression to Farm': 'The Tacet Suppression number in the F2 list.',
        }
        self.default_config = default_config
        self.door_walk_method = {  # starts with 0
            0: [],
            1: [],
            2: [],
            3: [],
            4: [],
            5: [],
            6: [["a", 0.3]],
            7: [["d", 0.6]],
            8: [["a", 1.5], ["w", 3], ["a", 2.5]],
        }
        self.stamina_once = 60

    def run(self):
        super().run()
        self.wait_in_team_and_world(esc=True)
        self.farm_tacet()

    def farm_tacet(self, daily=False, used_stamina=0, config=None):
        if config is None:
            config = self.config
        if daily:
            must_use = 180 - used_stamina
        else:
            must_use = 0
            
        # 為了計算總戰鬥次數，估算所需次數（每次消耗60）
        total_rounds = 1
        if daily and must_use > 0:
            total_rounds = math.ceil(must_use / self.stamina_once)
            
        from src.utils.ProgressFormatter import RunStatus
        self.info_incr('used stamina', 0)
        round_count = 0
        while True:
            round_count += 1
            self.sleep(1)
            gray_book_boss = self.openF2Book("gray_book_boss")
            self.click_box(gray_book_boss, after_sleep=1)
            current, back_up, total = self.get_stamina()
            if current == -1:
                self.click_relative(0.04, 0.4, after_sleep=1)
                current, back_up, total = self.get_stamina()
            if total < self.stamina_once:
                return self.not_enough_stamina()

            self.click_relative(0.18, 0.48, after_sleep=1)
            index = config.get('Which Tacet Suppression to Farm', 1) - 1
            
            if hasattr(self, 'formatter') and self.formatter and round_count == 1:
                self.formatter.add_node('tp', '傳送至目標地點', parent_id='farm')
                self.formatter.set_status('tp', RunStatus.RUNNING)
                
            self.teleport_to_tacet(index)
            self.wait_click_travel()
            self.wait_in_team_and_world(time_out=120)
            self.sleep(2)
            
            if hasattr(self, 'formatter') and self.formatter and round_count == 1:
                self.formatter.set_status('tp', RunStatus.DONE)
                
            combat_detail_id = f'combat_detail_{round_count}'
            combat_node_id = f'combat_{round_count}'
            if hasattr(self, 'formatter') and self.formatter:
                round_str = f"戰鬥 {round_count}/{total_rounds}" if daily else f"戰鬥 {round_count}"
                self.formatter.add_node(combat_node_id, round_str, parent_id='farm')
                self.formatter.set_status(combat_node_id, RunStatus.RUNNING)
                self.formatter.add_node(combat_detail_id, '正在跑圖', parent_id=combat_node_id)
                self.formatter.set_status(combat_detail_id, RunStatus.RUNNING)

            if self.door_walk_method.get(index) is not None:
                for method in self.door_walk_method.get(index):
                    self.send_key_down(method[0])
                    self.sleep(method[1])
                    self.send_key_up(method[0])
                    self.sleep(0.05)
                if hasattr(self, 'formatter') and self.formatter:
                    self.formatter.update_text(combat_detail_id, '正在向目標移動')
                in_combat = self.run_until(self.in_combat, 'w', time_out=10, running=True,
                                           target=False, post_walk=1)
                if not in_combat:
                    raise Exception('Tacet can not walk to combat')
            else:
                self.walk_until_f(time_out=4, backward_time=0, raise_if_not_found=True)
                self.pick_f(handle_claim=False)
                
            if hasattr(self, 'formatter') and self.formatter:
                self.formatter.update_text(combat_detail_id, '戰鬥中')
            
            start_time = time.time()
            self.combat_once()
            self.sleep(3)
            combat_time = int(time.time() - start_time)
            
            if hasattr(self, 'formatter') and self.formatter:
                self.formatter.update_text(combat_detail_id, '前往領取獎勵')
            self.walk_to_treasure()
            self.pick_f(handle_claim=False)
            can_continue, used = self.use_stamina(once=self.stamina_once, must_use=must_use)
            self.info_incr('used stamina', used)
            self.sleep(4)
            self.click(0.51, 0.84, after_sleep=3)
            
            if hasattr(self, 'formatter') and self.formatter:
                round_str_done = f"戰鬥 {round_count}/{total_rounds} (耗時 {combat_time} 秒)" if daily else f"戰鬥 {round_count} (耗時 {combat_time} 秒)"
                self.formatter.update_text(combat_node_id, round_str_done)
                self.formatter.set_status(combat_detail_id, RunStatus.DONE)
                self.formatter.set_status(combat_node_id, RunStatus.DONE)
                
            if not can_continue:
                return self.not_enough_stamina()
            must_use -= used

    def not_enough_stamina(self, back=True):
        self.log_info(f"used all stamina")
        if back:
            self.back(after_sleep=1)

    def teleport_to_tacet(self, index):
        self.info_set('Teleport to Tacet Suppression', index)
        if index >= self.total_number:
            raise IndexError(f'Index out of range, max is {self.total_number}')
        self.click_on_book_target(index + 1, self.total_number)
