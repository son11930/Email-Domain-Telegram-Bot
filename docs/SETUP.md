# ติดตั้งและเชื่อมบริการ

คู่มือนี้เป็นขั้นตอนให้เจ้าของทำกับบัญชีและ VPS ของตัวเอง ไม่ถือว่ามีการตั้งค่าหรือโอนเงินจริงแล้ว ทุก ID / โดเมน / key ในตัวอย่างเป็น placeholder ให้ใช้ข้อมูลบัญชีของตัวเองเท่านั้น

## 1. เตรียม VPS

แนะนำ Ubuntu 24.04 LTS และ Python 3.11+ ตรวจรุ่น VPS จริงก่อน: `cat /etc/os-release`, `python3 --version` และ `free -h` หากเป็น Ubuntu 20.04 ให้ตรวจ Python ที่ติดตั้งและแผน security updates; แนะนำอัปเกรดเป็น LTS ที่รองรับก่อน production เพราะ Python เริ่มต้นอาจต่ำกว่าที่โปรแกรมต้องการ เครื่อง 2 core / RAM 4 GB เริ่มด้วย bot, worker และ web อย่างละหนึ่งโปรเซส โดย bot และ web ต้องมี instance เดียว เพราะสถานะสนทนา/session อยู่ในหน่วยความจำ

การรันบน VPS ใช้ Python virtualenv และ GNU Screen โดยตรง ไม่ต้องติดตั้ง Docker ให้ใช้บัญชี Linux ที่ไม่ใช่ root สำหรับโปรแกรม และติดตั้งเครื่องมือ:

```sh
sudo apt update
sudo apt install -y screen python3-venv python3-pip unzip nginx certbot python3-certbot-nginx postgresql-client logrotate
```

สร้างบัญชี Linux แบบไม่มีสิทธิ์ root ชื่อ `team-mail` แล้ววาง source release ที่ `/opt/team-mail-bot`; ให้บัญชีนี้เป็นเจ้าของไฟล์โปรแกรมและ `.env` บริการทั้งสามจะทำงานด้วยบัญชีนี้ ตัวอย่างการสร้างบัญชีและแตก source archive:

```sh
sudo useradd --system --user-group --create-home --home-dir /opt/team-mail-bot --shell /usr/sbin/nologin team-mail
sudo unzip team-mail-bot-0.1.0-source.zip -d /opt/team-mail-bot
sudo chown -R team-mail:team-mail /opt/team-mail-bot
```

ตั้ง DNS `admin.example.com` ไป public IP ของ VPS แทนโดเมนในทุกไฟล์ด้วยโดเมนจริง เปิดเฉพาะ SSH ที่จำเป็นกับ 80/443 เว็บแอดมินใช้ `PORT=8001` และ bind `127.0.0.1` เพื่อไม่ชนกับบริการเดิมบนพอร์ต 8000 และไม่เปิดพอร์ตนี้ออกอินเทอร์เน็ต ไม่เปิด PostgreSQL บน VPS เพราะใช้ DB ภายนอก

## 2. สร้าง Supabase Free

1. สร้างบัญชีและ project เลือกแผน Free และ region ใกล้ VPS ตั้ง DB password ที่ไม่ซ้ำและเก็บใน password manager
2. กด **Connect → Session pooler** คัดลอก host / username / database / port ตาม project จริง ใช้ session mode สำหรับโปรเซสทำงานต่อเนื่อง IPv4 โดยทั่วไปเป็น 5432 ตาม [เอกสารการเชื่อมต่อ](https://supabase.com/docs/guides/database/connecting-to-postgres) ห้ามเดา region/host
3. เปลี่ยน prefix connection string เป็น `postgresql+psycopg://` แล้วเติม `?sslmode=require` URL-encode อักขระพิเศษใน password ก่อนประกอบ URL
4. คัดลอก Project URL และ publishable key จาก project settings ไป `SUPABASE_URL` / `SUPABASE_PUBLISHABLE_KEY` ค่านี้สำหรับ Auth ไม่ใช้ service-role key ใน browser
5. Authentication → ปิด **Allow new users to sign up** สร้างบัญชี admin เองใน Users ด้วยอีเมลและรหัสผ่าน ยืนยันอีเมลตามระบบ เลือก UUID ของ user ใส่ `WEB_ADMIN_SUBJECTS` ไม่ใช่ Telegram ID ดู [Auth configuration](https://supabase.com/docs/guides/auth/general-configuration)
6. กำหนด Site URL เป็นโดเมน HTTPS จริง ผู้ใช้ Telegram ทั่วไปยังเข้าใช้บอทได้ การปิด signup นี้จำกัดเฉพาะ Auth เว็บ

Free ที่ตรวจวันที่ 2026-10-20 มี DB 500 MB, egress 5 GB, พักหลังไม่ใช้งาน 1 สัปดาห์ และไม่มี automatic backup ตาม [ราคาของ Supabase](https://supabase.com/pricing) ตรวจราคา/โควตาอีกครั้งก่อนเปิดจริง ไม่จำเป็นต้องอัปเกรดเสียเงินเพื่อเริ่มต้น

ฐานข้อมูลเก็บข้อมูลการเงิน/คลังส่วนตัว ห้ามสร้าง anonymous policies ให้อ่านตารางเหล่านี้หรือเปิดสิทธิ์ผ่าน Data API โดยไม่มี RLS Backend ใช้ DB credential ใน `.env` เท่านั้น ดูการตรวจสิทธิ์หลังสร้างตารางในหัวข้อ 7

## 3. สร้าง Telegram bot และ admin IDs

สร้าง bot ผ่านบัญชี BotFather ทางการ เก็บ token ใน `TELEGRAM_BOT_TOKEN` ตั้ง `OWNER_ID` เป็น numeric Telegram ID ของเจ้าของจริง และ `ADMIN_IDS` เป็นตัวเลขคั่น comma ไม่มี `@username` หากไม่เพิ่มคนอื่นให้เว้นว่าง owner ยังมีสิทธิ์

ให้เจ้าของและสมาชิกทัก `/start` ในแชทส่วนตัวก่อนซื้อ ระบบสร้างบัญชีเครดิตศูนย์อัตโนมัติ บอทนี้ใช้ long polling จึงไม่ต้องตั้ง Telegram webhook และให้รัน bot instance เดียวต่อ token

## 4. Binance API สำหรับตรวจเงินเข้าอัตโนมัติ

1. เข้าบัญชีรับเงิน Binance ด้วยตัวเอง → Account / API Management → Create API เลือก system-generated HMAC key/secret ให้ตรงกับ connector
2. ตั้งชื่อแยก เช่น `Team-Mail-ReadOnly` เปิดสิทธิ์อ่านที่จำเป็นเท่านั้น จำกัด source IP เป็น public outbound IP ของ VPS ไม่เปิดซื้อขาย ถอน หรือโอน
3. บันทึก `BINANCE_API_KEY` และ `BINANCE_API_SECRET` ใน `.env` บน VPS ไม่ส่งใน Telegram/Discord หรือ commit เข้า Git
4. `BINANCE_RECEIVER_ID` คือ UID/Pay ID ของบัญชีรับจริง ตรวจชนิด ID และหน้าส่งเงินให้ตรงกัน ห้ามใช้หมายเลขจากภาพอ้างอิง
5. endpoint ที่ใช้คือ signed `GET /sapi/v1/pay/transactions` บน `BINANCE_BASE_URL` ไม่ใช่ Binance Pay Merchant API คู่มือ [Binance Get Pay Trade History](https://developers.binance.com/docs/pay/rest-api) และ [การสร้าง API key](https://www.binance.com/en/support/faq/detail/360002502072)
6. ตรวจเวลา VPS ให้ sync NTP หาก signature/time window ผิดให้แก้เวลาและตรวจ key/IP ห้ามเปิดสิทธิ์ถอนเพื่อแก้ permission error
7. เจ้าของทำรายการทดสอบเล็กด้วยตัวเอง: สร้างคำขอเติมในบอทแล้วโอนยอดที่แสดงทุกหลัก เช่นยอดสมมติ `1.0037 USDT` ตรวจว่า UI อนุญาต precision จริงและ API ของบัญชีรับมองเห็นรายการสำเร็จชนิดนี้ ตรวจเครดิตเพิ่มครั้งเดียวเท่ายอดรับจริง

การมี API key ไม่รับรองว่าบัญชี/ภูมิภาคอ่านรายการ UID แบบที่ต้องการได้ หาก API ไม่เห็นเงินเข้าหรือส่งทศนิยม 3–4 หลักไม่ได้ ให้หยุดเปิดรับเติมจนตรวจข้อจำกัดได้ ไม่เครดิตจากรูปสลิปหรือชื่อผู้โอน

## 5. Discord สองห้อง

สร้างห้องข้อความแยก เช่น `topup-events` กับ `order-events` ไป Edit Channel → Integrations → Webhooks → New Webhook คัดลอก URL ของแต่ละห้องใส่ `DISCORD_TOPUP_WEBHOOK_URL` และ `DISCORD_ORDER_WEBHOOK_URL` จำกัดสิทธิ์เข้าห้องให้ทีมที่จำเป็น URL webhook เป็น secret ที่ผู้ถือ URL ส่งข้อความได้ ดู [เอกสาร Discord webhook](https://docs.discord.com/developers/resources/webhook)

แจ้งเติมเมื่อบันทึกเครดิตสำเร็จ และแจ้ง order หลังบันทึกการซื้อ ไม่ใส่รหัสผ่านหรือรายชื่ออีเมลทั้งคลังใน Discord ต้องใส่ webhook ทั้งสองค่าให้ครบก่อนเริ่ม worker; ค่าเว้นว่างในตัวอย่างเป็นช่องรอกรอก ไม่ใช่โหมดข้ามการแจ้งเตือน

## 6. กรอก environment

จากโฟลเดอร์โปรเจคบน VPS:

```sh
umask 077
sudo -u team-mail touch .env
sudo chmod 600 .env
sudo -u team-mail nano .env
```

กรอกค่าตามหัวข้อ 2–5 ได้แก่ `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `WEB_ADMIN_SUBJECTS`, `TELEGRAM_BOT_TOKEN`, `OWNER_ID`, `ADMIN_IDS`, `BINANCE_API_KEY`, `BINANCE_API_SECRET`, `BINANCE_RECEIVER_ID`, `BINANCE_BASE_URL`, `DISCORD_TOPUP_WEBHOOK_URL` และ `DISCORD_ORDER_WEBHOOK_URL` ตั้ง `PRICE_CREDITS=0.30`, `TOPUP_PRECISION=4`, `TOPUP_TTL_SECONDS=480`, `PUBLIC_BASE_URL` และ `ALLOWED_HOSTS` ให้ตรงกับโดเมนจริง ส่วนค่า runtime อื่นใช้ค่าเริ่มต้นจากเอกสาร/โค้ดได้

สร้าง `SESSION_SECRET` ด้วย `openssl rand -hex 32` แล้วเก็บผลใน `.env` ไม่ส่งในแชท `PUBLIC_BASE_URL=https://admin.example.com` ต้องตรงโดเมนเว็บ และ `ALLOWED_HOSTS=admin.example.com` เป็น host ไม่มี scheme/port

`TOPUP_PRECISION=4` มีช่องเศษ 99 ช่องต่อยอดฐาน; โหมด 3 หลักมี 9 ช่อง ยอดสุทธิที่เคยออกจะไม่ถูกนำกลับมาใช้ใหม่ ช่องหมดให้เลือกยอดฐานอื่น เช่น `1.01` แทน `1.00` หรือติดต่อแอดมิน ห้ามลบประวัติจองยอดเพื่อคืนช่อง `TOPUP_TTL_SECONDS=480` ให้เวลาโอน 8 นาที อัตรา 1 USDT = 1 credit รวมเศษสุ่ม ราคาเริ่มต้น 0.30 credit/เมล

ต่อผู้ใช้มี pending ได้หนึ่งรายการ ขอรายการใหม่ห่างกันอย่างน้อย 60 วินาที และมีรายการที่ยังไม่ได้รับเครดิตได้สูงสุด 3 รายการในช่วง 24 ชั่วโมงย้อนหลัง รายการที่ paid แล้วไม่นับเพดานนี้ ข้อจำกัดช่วยลดการจองช่องทิ้ง แต่คนสร้างหลายบัญชียังใช้ช่องจนหมดได้ จึงต้องติดตามความจุและเหตุผิดปกติ

ไฟล์ `.env` มี secrets ห้ามแชร์หรือแนบใน log และห้ามใส่ไว้ใน source archive หรือ backup สาธารณะ

## 7. สร้างตารางและรัน

```sh
cd /opt/team-mail-bot
sudo -u team-mail python3 -m venv .venv
sudo -u team-mail .venv/bin/python -m pip install -r requirements.lock.txt
sudo -u team-mail .venv/bin/python -m pip install --no-deps -e .
sudo -u team-mail .venv/bin/team-mail init-db
```

`init-db` สร้างตารางเริ่มต้นด้วย CREATE TABLE และตั้งสิทธิ์ ไม่ได้อัปเกรดคอลัมน์/constraint ของตารางที่มีอยู่แล้ว รุ่นที่เปลี่ยน schema ต้องมี migration ที่กำหนดเวอร์ชันและขั้นตอนเฉพาะ อ่าน release notes และสำรองก่อน ห้ามรัน init-db แล้วถือว่า DB เก่าถูกอัปเกรดครบ สำหรับฐานที่มีอยู่ ให้สำรองก่อนแล้วรัน `migrations/20261021_widen_binance_transaction_ids.sql` หนึ่งครั้งก่อนเริ่มรุ่นนี้

`init-db` เปิด RLS และเพิกถอน public grants ของตารางแอป ตรวจ Supabase Dashboard ว่านโยบายยังปิดกั้น `anon` / `authenticated` อ่านหรือเขียนคลัง/ยอด/ledger โดยตรง อย่าเพิ่ม public policy เพื่อแก้ปัญหาการเชื่อมต่อ Backend ใช้ DB credential ของ server เท่านั้น

หลังตั้ง `.env` และสร้างตารางแล้ว ติดตั้ง systemd template ที่เปิด GNU Screen แยกสาม session และเริ่มใหม่เมื่อโปรเซสจบ:

```sh
sudo install -m 0644 deploy/team-mail@.service /etc/systemd/system/team-mail@.service
sudo install -m 0644 deploy/team-mail-logrotate /etc/logrotate.d/team-mail
sudo systemctl daemon-reload
sudo systemctl enable --now team-mail@bot.service team-mail@worker.service team-mail@web.service
sudo systemctl status team-mail@bot.service team-mail@worker.service team-mail@web.service
sudo -u team-mail screen -ls
```

systemd จะเริ่มทั้งสาม session หลัง VPS บูท และ restart session หากโปรเซสหยุดเอง ดู log ด้วย `sudo tail -n 100 /opt/team-mail-bot/logs/worker.log` หรือ `sudo tail -f /opt/team-mail-bot/logs/worker.log` ใช้ `sudo -u team-mail screen -r team-mail-bot` เพื่อเข้า session; กด `Ctrl-A` แล้ว `D` เพื่อ detach ให้โปรแกรมทำงานต่อ จัดการหยุด/เริ่มใหม่ด้วย `sudo systemctl stop team-mail@bot.service` และ `sudo systemctl restart team-mail@bot.service` ตามบริการที่ต้องการ อย่ากด `Ctrl-C` ใน session ระหว่างใช้งาน เพราะ systemd จะเปิด session ใหม่ตามนโยบาย restart

ตรวจสาเหตุเมื่อเริ่มไม่ได้ด้วย `sudo journalctl -u team-mail@worker.service -n 100 --no-pager` และดู application log ประกอบ ให้จำกัดสิทธิ์ directory `logs` เฉพาะบัญชีบริการและตรวจ log ก่อนแชร์เพื่อลบข้อมูลส่วนตัว

หากค่าบัญชีสำคัญยังว่าง/ผิด ระบบอาจปฏิเสธการเริ่มต้นหรือเชื่อมต่อไม่สำเร็จ ให้แก้ค่าจริงก่อน อย่าเปลี่ยนไป SQLite หรือปิดการตรวจสิทธิ์เพื่อให้รันผ่าน

## 8. HTTPS สำหรับเว็บ admin

ออก certificate ก่อนเปิดไฟล์ TLS ตัวอย่าง ใช้ nginx site ชั่วคราวที่มี `listen 80`, `server_name` ตรง DNS และ proxy ไป `127.0.0.1:8001` แล้วตรวจ `sudo nginx -t` จากนั้น reload nginx และรัน:

```sh
sudo certbot --nginx -d admin.example.com
```

เมื่อมี certificate แล้วคัดลอก `deploy/nginx.conf` ไป nginx site ของโดเมน แก้โดเมนและ certificate path ให้ตรง ตรวจ `sudo nginx -t` แล้ว `sudo systemctl reload nginx` ทดสอบ `sudo certbot renew --dry-run` พอร์ต 8001 ต้องเข้าได้จากเครื่อง VPS เท่านั้น; บริการเดิมบนพอร์ต 8000 ไม่ต้องเปลี่ยน

ห้ามล็อกอิน admin ผ่าน HTTP สาธารณะ เข้า HTTPS login ด้วย Supabase user ที่ owner สร้างและ UUID อยู่ใน `WEB_ADMIN_SUBJECTS` ตั้ง `WEB_HOST=127.0.0.1` เพื่อให้ Nginx proxy ไปยังเว็บบนเครื่องเดียวกัน หากแก้ `.env` ให้ restart ทั้งสาม unit ด้วย `sudo systemctl restart team-mail@bot.service team-mail@worker.service team-mail@web.service` เพื่อให้โปรเซสอ่านค่าใหม่

## 9. ทดลองก่อนเปิดให้ทีม

ใช้เมลสมมติของทีมที่มีสิทธิ์จัดการ เช่น `member01@sub.example.org` และบัญชีทดสอบ เริ่มจาก `/start` แล้ว admin เพิ่มเมลและปรับเครดิตพร้อมเหตุผล ตรวจซื้อด่วน ซื้อหลายเมล/ไฟล์ ประวัติ ส่งซ้ำ และสิทธิ์ผู้ใช้ธรรมดา จากนั้น owner ทำการโอนเงินจริงทดสอบเองตามหัวข้อ 4 ตรวจทั้งยอด ledger Discord สองห้อง และ restart worker แล้วไม่เพิ่มเครดิตซ้ำ

อย่าเปิดรับเงินจากสมาชิกจนทดสอบ Binance history / precision กับบัญชีจริงผ่าน ฐานข้อมูลทดสอบและ production ต้องแยกกัน ขั้นตอนเหล่านี้ต้องทำบน VPS/บริการจริงโดยเจ้าของหรือผู้ได้รับสิทธิ์ ไม่ใช่สิ่งที่สำเร็จอัตโนมัติจาก unit tests
