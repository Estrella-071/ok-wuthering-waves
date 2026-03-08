import time

from qfluentwidgets import FluentIcon

from src.task.BaseCombatTask import BaseCombatTask
from src.task.WWOneTimeTask import WWOneTimeTask


class DiagnosisTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group_name = "Diagnosis"
        self.group_icon = FluentIcon.UNIT
        self.description = "Diagnosis Problem, Performance Test, Run in Game World"
        self.name = "Diagnosis"
        self.start = 0

    def run(self):
        super().run()
        if not self.in_team()[0]:
            self.log_error('must be in game world and in teams, please check you game resolution is 16:9', notify=True)
            return
        self.load_hotkey(force=True)

        self.start = time.time()
        capture_cost = 0
        ocr_cost = 0
        while True:
            self.load_chars()
            char = self.get_current_char()

            if not char:
                self._internal_info.clear()
                self.info_set('Current Character', "None")
                self.start = time.time()
            else:
                start = time.time()
                self.reset_scene()
                self.next_frame()
                capture_cost += time.time() - start
                start = time.time()
                self.refresh_cd()
                ocr_cost += time.time() - start
                self.info_incr('Capture Frame Count')
                self.info_set('Capture Frame Rate', round(
                    self.info_get('Capture Frame Count') / (capture_cost or 1),
                    2))
                self.info_set('OCR', ocr_cost / self.info_get('Capture Frame Count'))
                self.info_set('Game Resolution', f'{self.frame.shape[1]}x{self.frame.shape[0]}')
                self.info_set('Current Character', str(char))
                self.info_set('Resonance CD', self.get_cd('resonance'))
                self.info_set('Echo CD', self.get_cd('echo'))
                self.info_set('Liberation CD', self.get_cd('liberation'))
                self.info_set('Concerto', char.get_current_con())

    def choose_level(self, start):
        y = 0.17
        x = 0.15
        distance = 0.08

        logger.info(f'choose level {start}')
        self.click_relative(x, y + (start - 1) * distance)
        self.sleep(0.5)

        self.wait_click_feature('gray_button_challenge', raise_if_not_found=True,
                                click_after_delay=0.5)
        self.wait_click_feature('gray_confirm_exit_button', relative_x=-1, raise_if_not_found=False,
                                time_out=3, click_after_delay=0.5, threshold=0.8)
        self.wait_click_feature('gray_start_battle', relative_x=-1, raise_if_not_found=True,
                                click_after_delay=0.5, threshold=0.8)
