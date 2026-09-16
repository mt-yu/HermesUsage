"""tests/ —— 让 `python -m unittest discover -s tests -t .` 能工作的包标记。

计划里没写这个文件，但 unittest 的规矩是：起始目录（-s）与顶层目录（-t）不同时，
起始目录必须是一个可导入的包。少了它，发现阶段直接
`ImportError: Start directory is not importable`，一条测试都跑不到。
"""
