@echo off
setlocal
cd /d "%~dp0"

echo [1/2] 同步依赖...
uv sync
if errorlevel 1 goto :fail

echo [2/2] 打包为单文件 exe...
uv run pyinstaller --noconfirm --clean git-repo-checker.spec
if errorlevel 1 goto :fail

echo.
echo 打包完成: %CD%\dist\git-repo-checker.exe
exit /b 0

:fail
echo.
echo 打包失败，请查看上方日志。
exit /b 1
