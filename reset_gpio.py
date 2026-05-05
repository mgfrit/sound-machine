import lgpio
import json
import sys

try:
    with open('config.json') as f:
        config = json.load(f)
    pins = (config['gpio']['group_buttons'] +
            config['gpio']['sound_buttons'] +
            [config['gpio']['bluetooth_button']])
    h = lgpio.gpiochip_open(0)
    for pin in pins:
        try:
            lgpio.gpio_free(h, pin)
        except Exception:
            pass
    lgpio.gpiochip_close(h)
    print("GPIO reset OK")
except Exception as e:
    print(f"GPIO reset warning: {e}")
sys.exit(0)
