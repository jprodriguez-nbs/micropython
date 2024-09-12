import ssd1306

_display = None


def poweroff():
    if _display is not None:
        _display.poweroff()

def get_display():
    return _display

def init_display(i2c):
    global _display
    try:
        _display = ssd1306.SSD1306_I2C(128, 64, i2c)
        #display.text('Hello, World!', 0, 0, 1)
        #display.show()

        _display.fill(0)
        _display.fill_rect(0, 0, 32, 32, 1)
        _display.fill_rect(2, 2, 28, 28, 0)
        _display.vline(9, 8, 22, 1)
        _display.vline(16, 2, 22, 1)
        _display.vline(23, 8, 22, 1)
        _display.fill_rect(26, 24, 2, 4, 1)
        _display.text('Urbidermis', 40, 0, 1)
        _display.text('Jardinera', 40, 12, 1)
        _display.text('', 40, 24, 1)
        _display.show()
    except:
        _display = None
        pass



def update_display(d):
    global _display
    if _display is not None:
        try:
            display_on = d[1]
            if display_on:
                l = d[0]
                _display.poweron()
                _display.fill(0)
                if l is not None:
                    n = len(l)
                    if n>0 and l[0] is not None:
                        _display.text(l[0], 0, 0, 1)
                    if n>1 and l[1] is not None:
                        _display.text(l[1], 0, 12, 1)
                    if n>2 and l[2] is not None:
                        _display.text(l[2], 0, 24, 1)
                    if n>3 and l[3] is not None:
                        _display.text(l[3], 0, 36, 1)
                    if n>4 and l[4] is not None:
                        _display.text(l[4], 0, 48, 1)
                _display.show()
            else:
                _display.poweroff()
        except:
            pass

def update_display_with_status(cls):
    try:
        display_data = cls.status.get_screen()
        update_display(display_data)
    except Exception as ex:
        cls.logger.exc(ex,"Failed to update_display_with_status: {e}".format(e=ex))



