"""`python -m horosa_skill …` 与 `horosa-skill …` 完全等价。

Windows 的 Smart App Control（应用控制）按云端信誉放行程序：uv / uvx 给每个环境现生成的 `Scripts\\horosa-skill.exe`
（trampoline，每份内容随安装路径不同 → 永远没有信誉）可能被拦，报 `(os error 4551)`；环境里的 `python.exe` 是解释器
自带的那份，不受影响。所以客户端配置在这类机器上写 `… python -m horosa_skill serve`，见 client_config.payload。
"""

from horosa_skill.surfaces.cli import app

if __name__ == "__main__":
    app(prog_name="horosa-skill")
