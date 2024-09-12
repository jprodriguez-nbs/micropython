# This list of frozen files doesn't include task.py because that's provided by the C module.
freeze(
    "..",
    (
        "MicroWebSrv2/__init__.py",
        "MicroWebSrv2/httpRequest.py",
        "MicroWebSrv2/httpResponse.py",
        "MicroWebSrv2/microWebSrv2.py",
        "MicroWebSrv2/webRoute.py",
        "MicroWebSrv2/libs/urlUtils.py",
        "MicroWebSrv2/libs/XAsyncSockets.py",
        "MicroWebSrv2/mods/PyhtmlTemplate.py",
        "MicroWebSrv2/mods/WebSockets.py",
    ),
    opt=3,
)
