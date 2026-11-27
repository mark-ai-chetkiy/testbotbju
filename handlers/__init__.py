from . import start, profile, food, photo, recipes, diary, misc


def register_all(dp):
    # порядок важен: меню и команды — первыми, свободный ввод — последним
    for m in (start, profile, food, photo, recipes, diary, misc):
        dp.include_router(m.router)
