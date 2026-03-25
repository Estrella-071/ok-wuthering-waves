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
        self.support_schedule_task = True
        self.config_description = {
            'Which Tacet Suppression to Farm': 'The Tacet Suppression number in the F2 list.',
        }
        default_config = {
            'Which Tacet Suppression to Farm': 1,  # starts with 1
        }
        default_config.update(self.default_config)
        self.default_config = default_config
        self.total_number = 16
        self.target_enemy_time_out = 10
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
        self.ensure_main(time_out=180)
        self.wait_in_team_and_world(esc=True)
        self.farm_tacet()

    def farm_tacet(self, daily=False, used_stamina=0, config=None, prefer_double=None):
        if config is None:
            config = self.config
        if prefer_double is None:
            prefer_double = self.stamina_config.get('Prefer Double Stamina', False)
        if daily:
            must_use = 180 - used_stamina
        else:
            must_use = 0
        self.info_incr('used stamina', 0)
        self.info_set('current task', self.tr('Farming Tacet Suppression'))
        while True:
            gray_book_boss = self.openF2Book("gray_book_boss", opened=False)
            
            self.wait_until(
                lambda: self.get_stamina(update_info=False)[0] != -1,
                pre_action=lambda: self.click_box(gray_book_boss, after_sleep=0.1),
                time_out=5, settle_time=0.1
            )
            current, back_up, total = self.get_stamina(update_info=False)
            if current == -1:
                self.wait_until(
                    lambda: self.get_stamina(update_info=False)[0] != -1,
                    pre_action=lambda: self.click_relative(0.04, 0.4, after_sleep=0.1),
                    time_out=3, settle_time=0.1
                )
                current, back_up, total = self.get_stamina(update_info=False)
            if total < self.stamina_once:
                return self.not_enough_stamina()

            index = config.get('Which Tacet Suppression to Farm', 1) - 1
            self.wait_until(
                lambda: self.get_stamina(update_info=False)[0] != -1,
                pre_action=lambda: self.click_relative(0.18, 0.48, after_sleep=0.1),
                time_out=5, settle_time=0.1
            )
            self.teleport_to_tacet(index)
            self.wait_click_travel()
            
            self.wait_in_team_and_world(time_out=120)
            if self.door_walk_method.get(index) is not None:
                for method in self.door_walk_method.get(index):
                    self.send_key_down(method[0])
                    self.sleep(method[1])
                    self.send_key_up(method[0])
                    self.sleep(0.05)
                in_combat = self.run_until(self.in_combat, 'w', time_out=10, running=True,
                                           target=False, post_walk=1)
                if not in_combat:
                    raise Exception('Tacet can not walk to combat')
            else:
                self.walk_until_f(time_out=4, backward_time=0, raise_if_not_found=True)
                self.pick_f(handle_claim=False)
            logger.debug('start combat')
            self.combat_once()
            self.sleep(3)
            logger.debug('claim reward')
            self.walk_to_treasure()
            self.pick_f(handle_claim=False)
            can_continue, used = self.use_stamina(once=self.stamina_once, must_use=must_use, prefer_double=prefer_double)
            self.sleep(4)
            self.click(0.51, 0.84, after_sleep=3)
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
