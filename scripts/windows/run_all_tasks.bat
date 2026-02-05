@echo off 
chcp 65001 >nul 
cd /d "D:\CODE\gupiao\guPiaoJiaoYi" 
echo [%DATE% %TIME%] 开始执行汇总任务 >> "D:\CODE\gupiao\guPiaoJiaoYi\auto_run.log" 
call "D:\CODE\gupiao\guPiaoJiaoYi\run_webhtml.bat" 
echo [%DATE% %TIME%] webhtml任务执行完毕 >> "D:\CODE\gupiao\guPiaoJiaoYi\auto_run.log" 
call "D:\CODE\gupiao\guPiaoJiaoYi\autoPython_bat.bat" 
echo [%DATE% %TIME%] 所有任务执行完毕 >> "D:\CODE\gupiao\guPiaoJiaoYi\auto_run.log" 
