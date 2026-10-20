# Team Mail Bot

Telegram bot for team-managed domain email inventory with credit-based purchases, Binance Pay top-ups, Discord notifications, and an admin web panel.

บอท Telegram แจกอีเมลโดเมนพร้อมเครดิตและเว็บแอดมิน ใช้ PostgreSQL ภายนอกบน Supabase และรัน bot / worker / web บน VPS ด้วย GNU Screen (ไม่ใช้ Docker เป็นขั้นตอนรันหลัก)

- ทุกคนเริ่มใช้งานผ่านแชทส่วนตัวได้; สิทธิ์เพิ่ม/ลบเมลและปรับเครดิตจำกัดเฉพาะแอดมิน
- ขอ 1 เมลด่วนหรือซื้อหลายเมล ราคาเริ่มต้น 0.30 credit/เมล
- ซื้อหลายเมลส่งไฟล์ `.txt` และข้อความครบทุกอีเมล
- เติม USDT ผ่าน Binance UID ด้วยยอดเฉพาะทศนิยม 3–4 หลัก; 1 USDT รับจริง = 1 credit
- แจ้งเติมเงินและซื้อผ่าน Discord webhook คนละห้อง
- เก็บเฉพาะอีเมล ตัดลำดับและส่วนรหัสผ่านจากข้อมูลนำเข้า

เริ่มต้นที่ [คู่มือติดตั้ง](docs/SETUP.md) และ [คู่มือดูแลระบบ](docs/OPERATIONS.md) รายละเอียดข้อกำหนดอยู่ใน [แผนงาน](plan.md)

สำหรับ VPS ให้ทำตามคำสั่งติดตั้งในคู่มือ ซึ่งใช้ systemd เปิด GNU Screen sessions ทั้งสามหลังบูทและ restart โปรเซสเมื่อจบเอง ยังเข้าไปดูแต่ละ session ได้ด้วย `screen -r`

## รันในเครื่องพัฒนา

ต้องมี Python 3.11+ และ PostgreSQL สำหรับทดสอบที่ไม่ใช่ฐานข้อมูลจริง

```sh
python -m venv .venv
```

Linux: `source .venv/bin/activate` / Windows PowerShell: `.venv/Scripts/Activate.ps1`

```sh
python -m pip install -r requirements.lock.txt
python -m pip install -e ".[dev]"
```

คัดลอก `.env.example` เป็น `.env` กรอกค่าจริงเฉพาะในเครื่อง แล้วเริ่มทีละโปรเซส:

```sh
team-mail init-db
team-mail bot
team-mail worker
team-mail web
```

ค่า HTTPS และ Supabase Auth ต้องตั้งครบก่อนใช้เว็บ ระบบไม่ได้สร้างบัญชีภายนอกหรือ deploy ให้เมื่อดาวน์โหลดโค้ด

เริ่มด้วย bot / worker / web อย่างละหนึ่ง instance โดยเฉพาะ bot และ web ต้องมีเพียง instance เดียว เพราะใช้สถานะสนทนาและ session ในหน่วยความจำ การ restart อาจต้องเริ่มขั้นตอนสนทนาหรือเข้าสู่ระบบใหม่ แต่เครดิตและคำสั่งซื้ออยู่ใน PostgreSQL

## การตรวจสอบ

```sh
python -m pytest --cov=team_mail_bot --cov-report=term-missing
```

กำหนด `TEST_DATABASE_URL` ให้ PostgreSQL ทดสอบแยกต่างหากเพื่อรันการทดสอบ PostgreSQL ที่ต้องใช้ฐานข้อมูลจริง ห้ามชี้ไป production ตรวจผล skip และรายงาน coverage ทุกครั้ง ไม่ถือว่าการทดสอบในหน่วยความจำยืนยันพฤติกรรมล็อก PostgreSQL แล้ว
