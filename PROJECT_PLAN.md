# Project Plan

อัปเดต: 2026-10-21

## งานเพิ่มเติม: เผยแพร่ source ไป GitHub

- สถานะ: เผยแพร่ source ไป `main` แล้ว; `.env.example` ถูก ignore และไม่อยู่ใน Git; README/คู่มือติดตั้งไม่อ้างไฟล์ที่ไม่เผยแพร่
- เป้าหมาย: `son11930/Email-Domain-Telegram-Bot`
- Git identity ใช้เฉพาะ repo นี้; ไม่เก็บอีเมลส่วนตัวในไฟล์โครงการ
- เผยแพร่ 42 ไฟล์ใน initial commit และ push การแก้เอกสารติดตั้งตามหลัง; ตรวจยืนยันว่า `main` ตรงกับ `origin/main`

## งานปัจจุบัน: ตรวจ code, database, security และ performance

- สถานะ: ตรวจและแก้ findings ที่ยืนยันแล้ว; tests 145 ผ่าน/6 PostgreSQL integration ข้ามเมื่อไม่มี TEST_DATABASE_URL, Ruff ผ่าน; ยังไม่ได้ deploy
- ขอบเขต: หา bug/ช่องโหว่/จุดคอขวดในโค้ดและ schema; แก้เฉพาะ findings ที่ทำซ้ำหรือยืนยันจากโค้ดได้
- ขั้นตอน: code review, database review, security review และ performance review → เพิ่ม regression tests ก่อนการแก้ → แก้ findings → รันชุดทดสอบที่เกี่ยวข้องและชุดหลัก → อัปเดต CHANGELOG
- ข้อจำกัด: ไม่ใช้ credentials จริง, ไม่แตะข้อมูล production, ไม่ deploy VPS และไม่เปลี่ยนพฤติกรรมระบบที่ไม่มีหลักฐานรองรับ

## งานปัจจุบัน: เตรียมติดตั้งบน VPS และเพิ่มคำสั่งอัปเดตจาก Windows

- สถานะ: ติดตั้ง prerequisites, clone repo, Python 3.11, dependencies, Screen/systemd และ logrotate เสร็จ; หยุดก่อน `.env` เพื่อให้เจ้าของใส่ secrets เอง; unit ยัง disabled จนตั้งค่าเสร็จ
- ขอบเขต: clone repo ลง `/opt/team-mail-bot`, สร้างบัญชี service, ติดตั้ง Screen/virtualenv/systemd และเพิ่มเมนู `git pull` + restart ใน `bot-manager.bat`
- ข้อจำกัด: ไม่อ่าน/สร้าง secrets, ไม่เปิดพอร์ต 8000, ไม่ตั้งค่า/ทดสอบธุรกรรมจริง

## งานเพิ่มเติม: เปลี่ยนวิธีรัน VPS เป็น screen

- สถานะ: เสร็จแล้ว อัปเดตคู่มือติดตั้ง/ดูแลระบบและ source archive แล้ว
- ขอบเขต: เพิ่ม systemd template ที่ควบคุม GNU Screen สำหรับ bot, worker และ web พร้อมเปิดหลัง boot/restart เมื่อโปรเซสจบ, ย้ายเว็บแอดมินไปพอร์ต localhost 8001, ตั้ง log rotation และอัปเดต README/คู่มือ/source archive
- ข้อกำหนด: ไม่ใช้ Docker เป็นขั้นตอนรันบน VPS; Docker templates ที่มีอยู่ไม่ใช่ทางติดตั้งหลัก
- หมายเหตุ: `screen -r` ยังใช้เข้าดู session ได้ ส่วน start/stop/restart ให้ใช้ `systemctl` เพื่อให้สถานะ unit ตรงกับ session
- ไม่เปลี่ยนโค้ดแอปหรือ schema; ไม่ deploy VPS จริงในงานนี้

## งานปัจจุบัน: ปรับแผนบอท Telegram เบิกอีเมลตามข้อกำหนดที่ยืนยัน

- สถานะ: พัฒนาโค้ดและทดสอบในเครื่องเสร็จ 2026-10-20 รอตั้งค่าบัญชีบริการและตรวจระบบจริงก่อนเปิดใช้งาน
- ขอบเขตรอบนี้: พัฒนาบอท เว็บแอดมิน ระบบเครดิต/คลัง/เติมเงินอัตโนมัติ Discord และเอกสารติดตั้งตาม plan.md
- แผนฉบับรายละเอียด: [plan.md](plan.md) เป็นแหล่งอ้างอิงหลักสำหรับงานนี้
- ข้อกำหนดยืนยัน: ทุกคนเริ่มใช้บอทได้, 1 USDT = 1 credit, อีเมลโดเมนประเภทเดียว ราคา 0.30 credit/เมล, แอดมินเท่านั้นปรับเครดิต/เพิ่มลบเมล
- ผลลัพธ์เพิ่มเติม: เติม Binance UID อัตโนมัติด้วยยอดสุ่มทศนิยม 3–4 หลัก, Supabase Free ภายนอก VPS, เว็บแอดมิน, Discord webhook สองห้อง และซื้อหลายเมลส่งทั้ง .txt หนึ่งไฟล์กับข้อความครบทุกเมล
- กฎที่ใช้: AGENTS.md, RULES.md และคำสั่งล่าสุดที่อนุมัติให้พัฒนาจนเสร็จ
- ขั้นตอน: สำรวจ → planner ตรวจข้อกำหนด → จัดทำ plan.md → ส่งให้เจ้าของตรวจ → รออนุมัติพัฒนา
- เงื่อนไขก่อนเริ่มโค้ด: เจ้าของอนุมัติแผนฉบับปรับปรุง; ราคาและสิทธิ์ยืนยันแล้ว ส่วนค่าระยะหมดอายุ/การกันยอดซ้ำเป็นข้อเสนอใน plan.md
- ข้อมูล VPS จากเจ้าของ: น่าจะ Ubuntu 20, CPU 2 core, RAM 4 GB; ต้องตรวจจริงก่อนติดตั้ง
- ทดสอบอัตโนมัติโดยไม่ส่งข้อความหรือโอนเงินจริง; บัญชี Supabase/Binance/Telegram/Discord และ VPS จริงต้องตั้งค่าด้วย credentials ของเจ้าของภายหลัง

## การแบ่งงานพัฒนา

- Core/database: PostgreSQL schema, ledger, inventory, orders, amount reservations และ transaction tests
- Payments: Binance signed history reader, reconciliation/checkpoints และ tests
- Telegram: เมนูภาษาไทย สิทธิ์ผู้ใช้/admin การนำเข้าและการซื้อ พร้อม handler tests
- Web: Supabase Auth, เว็บแอดมิน, CSRF และ authorization tests
- Integration: config, packaging, workers/outbox, Discord, deployment docs, security review และรวมผลทดสอบ

## ผลการพัฒนา

- [x] สมัครผู้ใช้ Telegram อัตโนมัติและแยกสิทธิ์แอดมิน
- [x] PostgreSQL schema, ledger, import เฉพาะ email, ลบรายอัน/เป็นชุด และ audit
- [x] ซื้อด่วน/หลายเมล, .txt และข้อความครบ, การส่งซ้ำจาก order เดิม
- [x] Signed Binance history reader, ยอดเฉพาะ 3–4 หลัก, checkpoint/reconciliation และกันเครดิตซ้ำ
- [x] เว็บแอดมิน Supabase Auth, CSRF, ปรับเครดิต ตั้งราคา คืนเครดิต และตรวจเงินค้าง
- [x] Discord สองห้อง, outbox พร้อม lease token/retry และปิดบัง secrets ใน log
- [x] 141 tests ผ่าน รวม PostgreSQL จริง 6 tests; coverage 92.24%; Ruff/pip check ผ่าน
- [x] Security/code review และแก้ findings ที่ยืนยัน พร้อมคู่มือและไฟล์ deploy (รอบตรวจเพิ่ม: 145 tests ผ่าน, 6 PostgreSQL integration ข้ามเมื่อไม่มี TEST_DATABASE_URL)
- [ ] เจ้าของสร้าง/ตั้งค่า Supabase, Telegram token, Binance read-only key/receiver, Discord webhooks และโดเมน
- [ ] ตรวจ Binance รับเงินจริง/precision/ประวัติในบัญชีจริง พร้อมทดสอบเล็กที่เจ้าของอนุญาต
- [ ] Deploy บน VPS, HTTPS, backup restore และ smoke test บริการจริง

ผลและข้อจำกัดการตรวจ: [docs/VALIDATION.md](docs/VALIDATION.md)

## ลำดับตั้งค่าบริการจริง

1. ตรวจความพร้อม Binance API/ทศนิยมรับจริงและ Supabase Free หลังอนุมัติเริ่มพัฒนา
2. โครงโปรเจค สมัครผู้ใช้ผ่าน Telegram อัตโนมัติ และสิทธิ์แอดมิน
3. PostgreSQL บน Supabase, ledger, นำเข้าอีเมล และเว็บแอดมิน
4. ขอ 1 เมลด่วน/หลายเมล และส่งซ้ำจากรายการเดิม
5. เติมอัตโนมัติด้วยยอดเฉพาะและ Discord webhook แยกสองห้อง
6. ทดสอบเส้นทางสำคัญ ตรวจความปลอดภัย และเตรียมรันบน VPS

รายละเอียดงาน เกณฑ์รับงาน และข้อที่ต้องตัดสินใจอยู่ใน plan.md เพื่อหลีกเลี่ยงการเก็บแผนซ้ำสองชุด
