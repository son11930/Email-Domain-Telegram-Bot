# Project Plan

อัปเดต: 2026-10-21

## งานเพิ่มเติม: เผยแพร่ source ไป GitHub

- สถานะ: เผยแพร่ source ไป `main` แล้ว; `.env.example` ถูก ignore และไม่อยู่ใน Git; README/คู่มือติดตั้งไม่อ้างไฟล์ที่ไม่เผยแพร่
- เป้าหมาย: `son11930/Email-Domain-Telegram-Bot`
- Git identity ใช้เฉพาะ repo นี้; ไม่เก็บอีเมลส่วนตัวในไฟล์โครงการ
- เผยแพร่ 42 ไฟล์ใน initial commit และ push การแก้เอกสารติดตั้งตามหลัง; ตรวจยืนยันว่า `main` ตรงกับ `origin/main`

## งาน: ตรวจ code, database, security และ performance

- สถานะ: ตรวจและแก้ findings ที่ยืนยันแล้ว; tests 145 ผ่าน/6 PostgreSQL integration ข้ามเมื่อไม่มี TEST_DATABASE_URL, Ruff ผ่าน; deployment จริงทำเสร็จตามหัวข้อด้านล่าง
- ขอบเขต: หา bug/ช่องโหว่/จุดคอขวดในโค้ดและ schema; แก้เฉพาะ findings ที่ทำซ้ำหรือยืนยันจากโค้ดได้
- ขั้นตอน: code review, database review, security review และ performance review → เพิ่ม regression tests ก่อนการแก้ → แก้ findings → รันชุดทดสอบที่เกี่ยวข้องและชุดหลัก → อัปเดต CHANGELOG
- ข้อจำกัด: การทดสอบอัตโนมัติไม่ใช้ credentials จริง; live smoke test ไม่สร้างธุรกรรมหรือส่งข้อความทดสอบไป Discord

## งาน: เตรียมติดตั้งบน VPS และเพิ่มคำสั่งอัปเดตจาก Windows

- สถานะ: ติดตั้ง prerequisites, clone repo, Python 3.11, dependencies, Screen/systemd และ logrotate เสร็จ; owner ตั้ง `.env` แล้ว และทุก unit เปิดใช้งาน/auto-start
- ขอบเขต: clone repo ลง `/opt/team-mail-bot`, สร้างบัญชี service, ติดตั้ง Screen/virtualenv/systemd และเพิ่มเมนู `git pull` + restart ใน `bot-manager.bat`
- ข้อจำกัด: `.env` อยู่บน VPS และไม่แสดงค่า; ไม่เปิดพอร์ต 8000 และไม่สร้างธุรกรรมเงินจริง

## งานเพิ่มเติม: เปลี่ยนวิธีรัน VPS เป็น screen

- สถานะ: เสร็จแล้ว อัปเดตคู่มือติดตั้ง/ดูแลระบบและ source archive แล้ว
- ขอบเขต: เพิ่ม systemd template ที่ควบคุม GNU Screen สำหรับ bot, worker และ web พร้อมเปิดหลัง boot/restart เมื่อโปรเซสจบ, ย้ายเว็บแอดมินไปพอร์ต localhost 8001, ตั้ง log rotation และอัปเดต README/คู่มือ/source archive
- ข้อกำหนด: ไม่ใช้ Docker เป็นขั้นตอนรันบน VPS; Docker templates ที่มีอยู่ไม่ใช่ทางติดตั้งหลัก
- หมายเหตุ: `screen -r` ยังใช้เข้าดู session ได้ ส่วน start/stop/restart ให้ใช้ `systemctl` เพื่อให้สถานะ unit ตรงกับ session
- ไม่เปลี่ยนโค้ดแอปหรือ schema ในงานเดิม; deployment จริงบันทึกไว้ในสถานะปัจจุบัน

## งานปัจจุบัน: ปรับแผนบอท Telegram เบิกอีเมลตามข้อกำหนดที่ยืนยัน

- สถานะ: deploy และตรวจ smoke test บน VPS เสร็จ (2026-10-21); รอ owner ล็อกอิน dashboard และทดสอบธุรกรรมจริงเมื่อพร้อม
- ขอบเขตรอบนี้: พัฒนาบอท เว็บแอดมิน ระบบเครดิต/คลัง/เติมเงินอัตโนมัติ Discord และเอกสารติดตั้งตาม plan.md
- แผนฉบับรายละเอียด: [plan.md](plan.md) เป็นแหล่งอ้างอิงหลักสำหรับงานนี้
- ข้อกำหนดยืนยัน: ทุกคนเริ่มใช้บอทได้, 1 USDT = 1 credit, อีเมลโดเมนประเภทเดียว ราคา 0.30 credit/เมล, แอดมินเท่านั้นปรับเครดิต/เพิ่มลบเมล
- ผลลัพธ์เพิ่มเติม: เติม Binance UID อัตโนมัติด้วยยอดสุ่มทศนิยม 3–4 หลัก, Supabase Free ภายนอก VPS, เว็บแอดมิน, Discord webhook สองห้อง และซื้อหลายเมลส่งทั้ง .txt หนึ่งไฟล์กับข้อความครบทุกเมล
- กฎที่ใช้: AGENTS.md, RULES.md และคำสั่งล่าสุดที่อนุมัติให้พัฒนาจนเสร็จ
- ขั้นตอน live setup: ตรวจชื่อคีย์ config โดยไม่แสดงค่า → เตรียม Supabase schema → เปิดบริการผ่าน systemd-managed GNU Screen → ตรวจ Telegram, worker, web, พอร์ต และ boot enablement → ตรวจ manager update flow
- ข้อกำหนดราคาและสิทธิ์ยืนยันแล้ว; ขอบเขตที่เหลือคือ owner ทดสอบเข้าสู่ระบบเว็บและยืนยันธุรกรรมจริง
- สเปก VPS ที่แจ้งไว้: Ubuntu 20 โดยประมาณ, CPU 2 core, RAM 4 GB; ยังไม่ได้ตรวจสเปกเครื่องจริงในรอบ deploy นี้
- ทดสอบอัตโนมัติโดยไม่ส่งข้อความหรือโอนเงินจริง; owner ตั้ง credentials บน VPS แล้ว โดยไม่เปิดเผยค่าใน repo/transcript

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
- [x] เจ้าของกรอกค่าลับใน `.env` บน VPS; ห้ามอ่านหรือแสดงค่าจริงใน transcript
- [x] Supabase schema initialized; bot และ worker เริ่มทำงานและตั้ง auto-start ผ่าน systemd
- [x] Web config ผ่าน validation; dashboard ตอบหน้า login HTTP 200 และ bind เฉพาะ loopback พอร์ต 8001
- [x] Deploy bot/worker/web; ทุก unit active และ enabled, มี GNU Screen 3 sessions
- [x] ตรวจ Telegram polling, worker reconciliation, dashboard login, log, พอร์ต 8000/8001 และ permission `.env`
- [x] ทดลอง flow อัปเดตชุดเดียวกับเมนู 5 ใน `bot-manager.bat`: pull, dependency install, init-db, enable และ restart ผ่าน
- [ ] ทดสอบ Supabase admin login ด้วยบัญชี owner, backup/restore และธุรกรรม Binance/Discord จริง

ผลและข้อจำกัดการตรวจ: [docs/VALIDATION.md](docs/VALIDATION.md)

## ลำดับตั้งค่าบริการจริง

1. ตรวจความพร้อม Binance API/ทศนิยมรับจริงและ Supabase Free หลังอนุมัติเริ่มพัฒนา
2. โครงโปรเจค สมัครผู้ใช้ผ่าน Telegram อัตโนมัติ และสิทธิ์แอดมิน
3. PostgreSQL บน Supabase, ledger, นำเข้าอีเมล และเว็บแอดมิน
4. ขอ 1 เมลด่วน/หลายเมล และส่งซ้ำจากรายการเดิม
5. เติมอัตโนมัติด้วยยอดเฉพาะและ Discord webhook แยกสองห้อง
6. Deploy บน VPS โดย systemd จัดการ GNU Screen; web bind เฉพาะ loopback ที่พอร์ต 8001 (พอร์ต 8000 สงวนให้ service เดิม)
7. ตรวจ Telegram, worker, dashboard, boot enablement และ manager update แล้ว; dashboard เปิดจาก public IP ผ่าน Nginx/HTTPS โดยเว็บยัง bind loopback ที่พอร์ต 8001
8. ทดสอบล็อกอิน dashboard และธุรกรรม Binance/Discord จริงแยกต่างหากเมื่อเจ้าของพร้อม

รายละเอียดงาน เกณฑ์รับงาน และข้อที่ต้องตัดสินใจอยู่ใน plan.md เพื่อหลีกเลี่ยงการเก็บแผนซ้ำสองชุด

## งานเพิ่มเติม: เปิดเว็บแอดมินจาก public IP ผ่าน HTTPS

- สถานะ: เสร็จแล้ว (2026-10-21)
- เป้าหมาย: เปิด dashboard ผ่าน IP โดยไม่ใช้โดเมนหรือส่ง session/password ผ่าน HTTP เปล่า
- แนวทาง: Nginx รับ public traffic บน 80/443 และ proxy ไป web ที่ `127.0.0.1:8001`; Certbot ใช้ Let's Encrypt short-lived IP certificate พร้อม auto-renew/reload
- ตรวจสอบ: GET จากภายนอกไป HTTP ได้ 301 ไป HTTPS; HTTPS ได้ 200 พร้อม trusted chain; timer เปิดใช้งานและ deploy hook reload Nginx
- ข้อจำกัด: certificate มีอายุประมาณ 160 ชั่วโมงและอาศัย auto-renew; ไม่เปลี่ยน listener ที่พอร์ต 8000 และไม่เปิด 8001 สู่ภายนอก

## งานเพิ่มเติม: ทำคำสั่งแอดมินปรับเครดิตให้กรอกง่าย

- สถานะ: เสร็จแล้ว (2026-10-21); tests Telegram ผ่านและ full suite ผ่าน 147 tests (6 PostgreSQL integration tests ข้ามเพราะไม่มี TEST_DATABASE_URL)
- ปัญหา: คำสั่งเดิมบังคับกรอก `USER_ID delta|target จำนวน เหตุผล` ในข้อความเดียว ทำให้ส่ง Telegram ID อย่างเดียวแล้วถูกปฏิเสธ
- เป้าหมาย: หลังเลือกปรับเครดิต ให้กรอก Telegram ID แล้วกรอกจำนวนเครดิตในข้อความถัดไป; บวกเพื่อเพิ่ม ลบเพื่อหัก และมีหน้าตรวจยอด/ปุ่มยืนยัน
- ข้อกำหนด: คง admin-only, ตรวจผู้ใช้และจำนวน, คง expected-balance guard, request idempotency, ledger/audit โดยใส่เหตุผลมาตรฐานอัตโนมัติ
- ผล: รองรับทั้ง `ID จำนวน` และการส่ง ID ก่อนแล้วค่อยส่งจำนวน; จำนวนบวกเพิ่ม จำนวนลบหัก; เหตุผล audit สร้างอัตโนมัติ และยังต้องยืนยัน/ตรวจยอดเดิมก่อนบันทึก
- ขั้นตอน: เพิ่ม regression tests ก่อน → ปรับ handler/state/prompt → รันทดสอบ Telegram และชุดหลัก → อัปเดต CHANGELOG

## งานเพิ่มเติม: ให้ bot-manager ใช้ SSH host key ที่บันทึกไว้

- สถานะ: เสร็จแล้ว (2026-10-21)
- ปัญหา: เมื่อเรียก manager จาก runtime ที่มี `USERPROFILE` คนละบัญชีกับ Windows profile ของเจ้าของ ระบบ SSH หา `known_hosts` เดิมไม่เจอและแสดง prompt ยืนยัน host ใหม่
- เป้าหมาย: manager ระบุไฟล์ known_hosts ชัดเจน, ตรวจ host key แบบเข้มงวด และแจ้งแนวทางตั้ง `TEAM_MAIL_SSH_KNOWN_HOSTS` เมื่อรันจาก profile แยก
- ขอบเขต: ไม่ปิด `StrictHostKeyChecking`, ไม่บันทึก private key/ข้อมูลลับลง repo, คำสั่ง SSH ทุกเมนูใช้ตัวเลือกชุดเดียวกัน
- วิธีตรวจ: ตรวจทุก invocation ของ ssh ใน batch file ให้ใช้ known_hosts เดียวกันและ `StrictHostKeyChecking=yes`; ตรวจ whitespace ด้วย `git diff --check`
- ผล: เพิ่ม override `TEAM_MAIL_SSH_KNOWN_HOSTS`, fallback ไปยัง `%USERPROFILE%\.ssh\known_hosts`, ปฏิเสธการเชื่อมต่อเมื่อไม่มีไฟล์ และกำหนด host-key verification ในทุกเมนู SSH

## งานเพิ่มเติม: แจ้งผลคำสั่งซื้อใน Discord และแสดงชื่อผู้ใช้

- สถานะ: เสร็จแล้ว (2026-10-21)
- ปัญหา: Discord ได้รับ event สถานะส่ง `pending` ตอนสั่งซื้อ แต่ไม่มี event success เมื่อ Telegram ส่งเมลครบ และแจ้งเฉพาะ Telegram ID
- เป้าหมาย: ไม่ส่ง pending order notification; ส่ง success เมื่อการส่งอีเมลครบทุกส่วน, ส่งสถานะยกเลิก/คืนเครดิตเมื่อแอดมินคืนรายการ และแสดงชื่อผู้ใช้คู่กับ Telegram ID ทั้งรายการซื้อและเติมเครดิต
- ข้อกำหนด: คง durable outbox/idempotency; หยุดส่ง legacy pending order events ที่ยังค้าง; ไม่เผยอีเมลหรือรหัสผ่านใน Discord
- หมายเหตุ: ความล้มเหลวชั่วคราวของ Telegram จะ retry ตามกลไกเดิม จึงยังไม่ถือเป็น terminal failure; Discord แจ้งไม่สำเร็จเมื่อรายการถูกคืนเครดิต/ยกเลิกโดยแอดมิน
- ผล: ย้าย success event ไปหลังส่งเมลครบ, เพิ่ม failure event ตอนคืนเครดิต, รวมชื่อกับ ID ในรายการซื้อ/เติมเงิน และปิด legacy pending order events ที่ยังค้างใน outbox
- ขั้นตอน: เพิ่ม regression tests ก่อน → เปลี่ยน enqueue จุดส่ง Discord → เพิ่มชื่อจาก User → ทดสอบ worker/core/e2e → อัปเดต CHANGELOG

## งานเพิ่มเติม: แสดงชื่อผู้ใช้บนหน้าแรกของ Telegram

- สถานะ: เสร็จแล้ว (2026-10-21)
- เป้าหมาย: แสดงชื่อ Telegram คู่กับ ID ในข้อความหลักที่เปิดด้วย `/start` หรือ `/menu`
- ข้อกำหนด: ใช้ชื่อจากข้อมูลผู้ใช้ที่บันทึกไว้, จัดการชื่อว่าง และไม่เปลี่ยนเมนูหรือยอดเครดิต
- ขั้นตอน: เพิ่ม regression test สำหรับข้อความหน้าแรก → แสดงชื่อ → รันทดสอบ Telegram และชุดหลัก → อัปเดต CHANGELOG
- ผล: หน้า `/start` และ `/menu` แสดงชื่อที่จัดรูป whitespace แล้ว (หรือ “ไม่ระบุชื่อ”) พร้อม Telegram ID โดยไม่เปลี่ยนยอดหรือปุ่มเมนู
