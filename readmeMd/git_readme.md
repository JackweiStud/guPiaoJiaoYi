# 22 端口受阻


git remote -v

### 后续直接用这两条（一条 pull，一条 push）
```powershell
git pull origin main
```
```powershell
git push origin main
```

先执行一次性的“永久修复”（把远程改为 SSH 走 443），之后就一直用上面两条：
```powershell
git remote set-url origin "ssh://git@ssh.github.com:443/JackweiStud/guPiaoJiaoYi.git"
```

可选：如果你不想改远程配置，每次用“一次性覆盖远程”的单条命令也行：
```powershell
git -c remote.origin.url="ssh://git@ssh.github.com:443/JackweiStud/guPiaoJiaoYi.git" pull origin main
```
```powershell
git -c remote.origin.url="ssh://git@ssh.github.com:443/JackweiStud/guPiaoJiaoYi.git" push origin main
```



powershell

ssh -T -p 443 git@ssh.github.com -v

cd D:\code-touzi\gitHub\guPiaoJiaoYi
git remote set-url origin "ssh://git@ssh.github.com:443/JackweiStud/guPiaoJiaoYi.git"
git fetch origin
git push origin main