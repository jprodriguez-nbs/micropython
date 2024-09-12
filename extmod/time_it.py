import uasyncio as asyncio
import utime

# Decorator to time function
# https://docs.micropython.org/en/latest/reference/speed_python.html
def timed_function(f, *args, **kwargs):
    myname = str(f).split(' ')[1]
    def new_func(*args, **kwargs):
        t = utime.ticks_us()
        result = f(*args, **kwargs)
        delta = utime.ticks_diff(utime.ticks_us(), t)
        print('Function {} Time = {:6.3f}ms'.format(myname, delta/1000))
        return result
    return new_func


# https://gist.github.com/Integralist/77d73b2380e4645b564c28c53fae71fb
def asynctimeit(func):
    async def helper(*args, **params):
        start = utime.ticks_us()
        result = await func(*args, **params)
        delta = utime.ticks_diff(utime.ticks_us(), start)
        print('Function {} Time = {:6.3f}ms'.format(func.__name__, delta/1000))
        return result

    return helper