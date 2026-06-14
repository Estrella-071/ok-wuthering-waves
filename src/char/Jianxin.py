import time
from src.char.BaseChar import BaseChar


class Jianxin(BaseChar):

    def cast_forte(self):
        self.heavy_attack(0.6)
        self.sleep(0.25)
        self.send_resonance_key()
        self.sleep(0.1)

    def cast_resonance(self):
        self.send_resonance_key()
        self.record_resonance_use()
        self.sleep(0.1)

    def do_perform(self):
        if self.is_forte_full():
            self.cast_forte()
        elif self.liberation_available():
            self.click_liberation()
            start_time = time.time()
            while time.time() - start_time < 2.0:
                if self.is_forte_full():
                    self.cast_forte()
                    break
                self.task.click()
                self.sleep(0.1)
                self.task.next_frame()
        else:
            if self.resonance_available():
                self.cast_resonance()
                self.send_resonance_key()
                self.sleep(0.1)
            else:
                self.continues_normal_attack(1)
            if self.echo_available():
                self.click_echo(time_out=0)

        main_dps = next((char for char in self.task.chars if char and char.is_main_dps and char != self), None)
        if self.is_con_full() and main_dps and main_dps.time_elapsed_accounting_for_freeze(main_dps.last_switch_time) < 1.0:
            self.task.next_frame()
            self.do_perform()
            return

        self.switch_next_char()
