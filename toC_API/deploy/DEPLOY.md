# real_toc Partner API 服务器部署指南

适用于 Linux（Ubuntu 22.04+）。API 进程只负责 HTTP；分析任务在服务器上子进程执行 `main.py`。

## 1. 架构（无域名 + Nginx）

```
合作方 → http://公网IP (80) → Nginx → uvicorn (127.0.0.1:8765) → api_server.py
                                                      └→ subprocess: main.py
```

- **8765 只监听本机**；公网只开放 **80**（HTTP）。
- 无 HTTPS：Partner Key 明文传输，仅适合试调/内网；有域名后见 `nginx-real-toc-domain-https.conf.example`。
- OpenAI Key、Partner API Key 勿提交 Git。

## 2. 服务器要求


| 项目     | 建议                        |
| ------ | ------------------------- |
| 系统     | Ubuntu 22.04 / Debian 12  |
| Python | 3.10+                     |
| 内存     | ≥ 4GB（并发 2 路 LLM 时建议 8GB） |
| 磁盘     | ≥ 20GB                    |
| 出站网络   | 能访问 OpenAI API            |


## 3. 安装步骤

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx

cd /root/toC_API   # 代码根目录
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
# requirements.txt 已包含 requirements-api.txt（fastapi / uvicorn）
```

创建环境变量文件（systemd 会读取；路径与 `real-toc-api.service` 中 `EnvironmentFile` 一致）：

```bash
sudo mkdir -p /etc/real-toc
sudo cp deploy/real-toc-api.env.example /etc/real-toc/real-toc-api.env
sudo chmod 600 /etc/real-toc/real-toc-api.env
# 按需编辑 REAL_TOC_DATA_ROOT、REAL_TOC_PARTNER_API_KEY 等
sudo nano /etc/real-toc/real-toc-api.env
```

## 4. 配置


| 项                                           | 无域名建议值                                                           |
| ------------------------------------------- | ---------------------------------------------------------------- |
| `openai.*`                                  | 有效 Key / org                                                     |
| `partner_api.api_keys`                      | 强随机；可为字符串或带 `success_quota` 的对象                                  |
| `partner_api.default_api_key_success_quota` | 各 Key 默认成功次数上限（`enabled` / `max_successful_requests` / `period`） |
| `partner_api.host`                          | 由 `.env` 设为 `127.0.0.1` 即可                                       |
| `partner_api.data_root`                     | `data/partner_trials`                                            |
| `security.allowed_origins`                  | `["http://8.216.48.250"]`（浏览器跨域；纯后端可忽略）                          |


```bash
sudo mkdir -p /var/lib/real_toc/partner_trials
sudo chown realtoc:realtoc /var/lib/real_toc/partner_trials
```

## 5. systemd 常驻

```bash
sudo cp deploy/real-toc-api.service /etc/systemd/system/
# 确认 WorkingDirectory、ExecStart 路径与服务器代码目录一致（默认 /root/toC_API）
# 确认 /etc/real-toc/real-toc-api.env 已创建（见 §3）
sudo systemctl daemon-reload
sudo systemctl enable --now real-toc-api
sudo systemctl status real-toc-api
curl -s http://127.0.0.1:8765/health
```

## 6. Nginx（无域名，IP + HTTP）

```bash
sudo cp deploy/nginx-real-toc.conf.example /etc/nginx/sites-available/real-toc
sudo ln -sf /etc/nginx/sites-available/real-toc /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

## 7. 防火墙

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw enable
# 不要 ufw allow 8765
```

云厂商安全组同样只放行 **22、80**。

## 8. 验证

```bash
# 本机 api
curl -s http://127.0.0.1:8765/health

# 经 Nginx（公网 IP 8.216.48.250）
curl -s http://8.216.48.250/health
curl -s -H "Authorization: Bearer <PartnerKey>" http://8.216.48.250/v1/questions
curl -s -H "Authorization: Bearer <PartnerKey>" http://8.216.48.250/v1/quota
```

浏览器：`http://43.165.186.13/docs`

## 9. 以后有域名

改用 `deploy/nginx-real-toc-domain-https.conf.example`，并：

```bash
sudo certbot --nginx -d api.yourdomain.com
```

## 10. 运维

- 日志：`journalctl -u real-toc-api`；任务日志 `{data_root}/.../api_pipeline.log`
- 改配置：`sudo systemctl restart real-toc-api` 或 `reload nginx`
- 配额文件：`{data_root}/_quota/success_counts.json`（`api_keys` 字段，按 Key hash 计数）

