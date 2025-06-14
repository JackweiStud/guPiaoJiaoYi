# guPiaoJiaoYi
AI和量化投资探索

说明：
定期更新 
pip install --upgrade akshare
certifi：pip install --upgrade certifi


#sdd.py 股票 策略相关测试


#mailFun.py 邮件触发系统

#autoProcess.py 固定股票策略查询后，当前是否出现买卖信号后，触发邮件系统
![Uploading image.png…]()


## 本地PC若无法发生email网络诊断
1、VPN设置为全局网络
2、步骤：在 Windows 防火墙中创建出站规则
打开高级防火墙设置
按下键盘上的 Windows 键，直接输入 "防火墙"。
在搜索结果中，点击 "高级安全 Windows Defender 防火墙"。
新建出站规则
在打开的窗口左侧，点击 "出站规则"。
在窗口的右侧，点击 "新建规则..."。
选择规则类型
选择 "端口"，然后点击 "下一步"。
指定协议和端口
选择 "TCP"。
选择 "特定远程端口"。
在输入框中填入：587, 465 (用逗号隔开)
点击 "下一步"。
选择操作
选择 "允许连接"，然后点击 "下一步"。
选择配置文件
保持所有三个选项（域、专用、公用）都勾选，点击 "下一步"。
命名规则
给这个规则起一个你能看懂的名字，比如 Allow Gmail SMTP。
点击 "完成"。

#powershell
Test-NetConnection -ComputerName smtp.gmail.com -Port 465