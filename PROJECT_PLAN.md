# Project Plan

## งานติดตาม: แก้หน้า Reports PostgreSQL GroupingError และตรวจสอบรายการ Telegram 19:08

- สถานะ: แก้และ review แล้ว; กำลัง deploy (2026-10-26)
- เป้าหมาย: แก้ `/reports` ที่ตอบ Internal Server Error และอธิบายว่ารายการ Telegram เวลา 19:08 ที่ผู้ใช้เห็นแต่ไม่เห็นเป็นแถวใหม่ใน `/orders` คืออะไร
- หลักฐาน: web log บน VPS ระบุ PostgreSQL `GroupingError` ใน partial-delivery aggregation เพราะ SELECT/GROUP BY สร้าง JSON `order_id` expression แยกกัน; ภาพ `/orders` แสดง order ID `a446…` ที่เวลา 18:52:49 และ ID ใหม่ `1a974…` ที่ 19:10:28 ขณะที่ข้อความ Telegram 19:08 อ้าง ID `a446…` เดิม
- แผน: เพิ่ม regression test ให้ยืนยันว่า SQLAlchemy ใช้ bind expression เดียวกันใน SELECT/GROUP BY; แก้ query โดยสร้าง expression เดียวแล้ว reuse; ทดสอบชุดที่เกี่ยวข้องและ full suite; deploy ผ่าน `bot-manager.bat` และตรวจ status/services กับ `/reports`
- ความเสี่ยง: PostgreSQL integration tests ต้องใช้ test database แยก ห้ามใช้ production database เพื่อรัน tests; อย่าถือข้อความ Telegram ที่อ้าง ID เก่าว่าเป็นการสร้าง order ใหม่

## งานเพิ่มเติม: แจ้งส่งเมลไม่สำเร็จและคืนเครดิตเฉพาะส่วน

- สถานะ: deploy ผ่าน bot-manager แล้ว (2026-10-26); bot/worker/web active
- เป้าหมาย: แจ้งผู้ซื้อเมื่อ Telegram ปฏิเสธการส่งอีเมลอย่างชัดเจน และคืนเครดิตเฉพาะจำนวนเมลที่ไม่ได้ส่ง; แสดงสถานะไม่สำเร็จใน dashboard
- ขอบเขต: แยก outbox ของเนื้อหาอีเมลออกจากข้อความสรุป/ไฟล์สำรอง; retry ความผิดพลาดชั่วคราวหรือผลลัพธ์คลุมเครือ; ห้ามคืนเต็มเมื่อส่งบางส่วนแล้ว; ป้องกัน resend ของออเดอร์ที่คืนเครดิตแล้ว
- วิธีทำ: เพิ่ม metadata จำนวนเมล/สิทธิ์คืนเครดิตต่อ outbox part, ปิดงานเฉพาะการ reject ถาวร, refund ledger แบบ idempotent ต่อ part, แจ้งยอดคืน/ยอดคงเหลือ และ final order state เมื่อ email part จบ; แยกการส่งซ้ำซึ่งคืนเครดิตไม่ได้และกันคำขอซ้ำขณะงานยัง active; ปรับรายงานคืนเครดิต/ส่งบางส่วน
- วิธีตรวจ: 245 tests ผ่าน, 9 PostgreSQL integration tests ข้ามเพราะไม่มี `TEST_DATABASE_URL`; Ruff และ `git diff --check` ผ่าน; code review ไม่พบ blocker
- ความเสี่ยง: timeout อาจเกิดหลัง Telegram รับข้อความแล้ว จึงห้าม refund จาก timeout/network error; แจ้งเตือนลูกค้าอาจส่งไม่ได้หากบล็อกบอท

## งานเพิ่มเติม: ปรับอัตราเติมเงินธนาคารและแก้ผ่านเว็บ

- สถานะ: deploy ผ่าน bot-manager; bot/worker/web active และ dashboard HTTP 200; 224 tests ผ่าน, 9 PostgreSQL integration tests ข้ามเพราะไม่มี `TEST_DATABASE_URL`; Ruff ผ่าน
- เป้าหมาย: เปลี่ยนอัตราเริ่มต้นจาก 33.50 เป็น 34.50 บาทต่อ 1 credit และให้แอดมินแก้เรตได้จากหน้า Settings ของ dashboard
- วิธีทำ: เก็บเรตเป็นจำนวนสตางค์ใน `settings`, ใช้เรตปัจจุบันตอนสร้างคำขอใหม่ และผ่านขั้นตรวจสอบ/ยืนยันพร้อมบันทึก audit
- ความเข้ากันได้: คำขอที่สร้างไว้แล้วคงยอดเครดิตที่บันทึกไว้; ไม่ต้องเปลี่ยน schema หรือ migration
- ตรวจสอบ: เพิ่ม tests ก่อน implementation สำหรับ conversion, การคงยอดคำขอเดิม, persistence/audit และหน้าเว็บ; จากนั้นรัน tests ที่เกี่ยวข้อง, full suite และ Ruff

## งานเพิ่มเติม: ทำให้ Telegram user ID คัดลอกง่าย

- สถานะ: deploy ผ่าน manager แล้ว; bot, worker, web และ Screen ทั้งสาม active; review ผ่าน; 201 tests ผ่าน, 7 PostgreSQL integration tests ข้ามเพราะไม่มี `TEST_DATABASE_URL`; Ruff ผ่าน
- ขอบเขต: แสดง Telegram user ID ในข้อความหน้าแรกเป็นช่องคัดลอกของ Telegram โดยคงชื่อ ยอดเครดิต และเมนูเดิม
- ตรวจ regression test และชุด Telegram เต็ม; อัปเดตผ่าน manager และตรวจ service/Screen ครบสามตัว

## งานเพิ่มเติม: ปรับข้อความโอนเงินและชื่อบริการ

- สถานะ: deploy ผ่าน manager แล้ว; bot, worker, web active; review ผ่าน; 201 tests ผ่าน, 7 PostgreSQL integration tests ข้ามเพราะไม่มี `TEST_DATABASE_URL`; Ruff ผ่าน
- ขอบเขต: แสดงเลขบัญชีและยอดโอนเป็นช่องคัดลอกง่าย ตัดชื่อผู้ให้บริการตรวจสลิปออกจากข้อความผู้ใช้ และเปลี่ยน branding ที่ผู้ใช้เห็นเป็น Nethinat Mail Service
- ตรวจ regression tests ของ Telegram และหน้า admin; อัปเดต VPS ผ่านขั้นตอน manager และตรวจ service/Screen ครบสามตัว

## งานเพิ่มเติม: แสดงชื่อธนาคารใน Telegram

- สถานะ: เสร็จแล้ว; `BANK_NAME` เป็นตัวเลือกและจะแสดงในคำแนะนำโอนเงินเมื่อมีค่า
- ขอบเขต: อ่าน `BANK_NAME` จาก `.env` และแสดงในคำแนะนำโอนเงินผ่านธนาคาร โดยคงการแสดงชื่อ/เลขบัญชีและการตรวจสลิปเดิม
- ตรวจด้วย regression test สำหรับข้อความฝากเงิน; Telegram/config 43 tests ผ่าน และ Ruff ผ่าน

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

## งานเพิ่มเติม: แสดงจำนวนเครดิตและยอดเติมเงินในเว็บแอดมินแบบอ่านง่าย

- สถานะ: เสร็จแล้ว (2026-10-21)
- ปัญหา: ตารางเติมเงินและคำสั่งซื้อแสดงค่าหน่วยย่อย เช่น `30000000` ตรง ๆ ทำให้อ่านยอดไม่สะดวก
- เป้าหมาย: แสดงค่าคอลัมน์ `*_units` เป็นหน่วยเต็มทศนิยมในหน้าเว็บแอดมิน พร้อมระบุ `credit` หรือ `USDT` ให้ชัดเจน
- ข้อกำหนด: คงเก็บข้อมูลจำนวนเต็ม 1e-8 ในฐานข้อมูลและใช้ในการคำนวณทั้งหมด; `price_units`/`total_units` เป็น credit ส่วน `base_units`/`expected_units` เป็น USDT
- ขั้นตอน: เพิ่ม regression tests ในหน้า orders/topups → format เฉพาะตอนแสดงผล → รัน web/full suite และ lint → อัปเดต CHANGELOG
- ผล: ตารางเว็บแอดมินแปลงค่าหน่วยย่อยให้เป็นทศนิยมและติดป้าย credit/USDT; ไม่แก้ข้อมูลที่จัดเก็บหรือการคำนวณ

## งานเพิ่มเติม: ปรับ Discord, เวลาและสถานะเติมเงินบนหน้าเว็บแอดมิน

- สถานะ: เสร็จแล้ว (2026-10-22)
- เป้าหมาย:
  1. ไม่ส่ง Discord order notification เมื่อผู้ซื้อเป็น owner/admin แต่ flow ส่งเมลใน Telegram ยังทำงานเหมือนเดิม
  2. แสดงวันที่เป็นเวลาไทย (Asia/Bangkok) เฉพาะบนหน้าเว็บ
  3. แปล action และรายละเอียด audit เป็นภาษาไทยที่อ่านง่าย พร้อมแสดงจำนวนเครดิตเป็นทศนิยม
  4. เปลี่ยน top-up ที่พ้นเวลารอเป็น `expired` อัตโนมัติ แม้ไม่มีการสร้างคำขอเติมเงินใหม่ และไม่ให้เครดิตหาก Binance บันทึกเวลารับเงินนอกช่วงคำขอ
  5. เปลี่ยนการ์ด dashboard จากคำขอเติมเงิน pending เป็นจำนวน payment ที่เติมเครดิตสำเร็จ
- ข้อกำหนด: เก็บ timestamp UTC และจำนวนเงินหน่วยย่อยเดิมในฐานข้อมูล; audit output ต้อง escape; คำขอหมดอายุที่มี payment timestamp อยู่ในช่วงคำขอเดิมยังตรวจ/จับคู่ได้ แม้ poller พบช้า; คง amount lease ไว้เพื่อป้องกันการจับคู่ยอดเก่าผิดคน
- ขั้นตอน: เพิ่ม regression tests สำหรับ core/worker/dashboard/template → เพิ่ม admin IDs ให้ service → ต่ออายุสถานะใน payment poll → ปรับการแสดงผลในเว็บ → รัน tests, lint และ review → อัปเดต CHANGELOG
- ผล: Discord ข้ามผู้ซื้อที่เป็น owner/admin, หน้ารายการในเว็บแสดงเวลาไทยและสถานะภาษาไทย, audit แสดงข้อความอ่านง่ายพร้อมจำนวนเครดิตแทน raw dict และหน้า top-up หมดอายุคำขออัตโนมัติ; dashboard แสดงจำนวน payment ที่เติมสำเร็จ
- การตรวจสอบ: `pytest --cov=team_mail_bot` ผ่าน 160 tests, ข้าม 6 PostgreSQL tests เพราะไม่มี `TEST_DATABASE_URL`, coverage รวม 91%; Ruff และ `git diff --check` ผ่าน
- หมายเหตุการ review: เรียก code-reviewer agent แล้ว แต่ agent runtime ปฏิเสธโมเดลที่ไม่รองรับ จึงตรวจ diff และรัน regression/full suite ในเครื่องแทน

## แผนงาน: เพิ่มเติมเงินผ่านบัญชีธนาคารด้วย SlipOK

- สถานะ: implementation และ automated verification; ยังไม่เปิดใช้ live SlipOK จนกว่าจะตั้งค่า API key/branch บน VPS และตรวจบัญชีจริง
- เป้าหมาย: เพิ่มวิธีเติมเงินผ่านบัญชีธนาคารและตรวจสลิปด้วย SlipOK ควบคู่กับ Binance Pay UID โดยไม่กระทบ flow Binance ปัจจุบัน
- ขอบเขตและมาตรการ:
  1. แยก provider/method ของคำขอเติมเงินให้ชัดเจน เพื่อไม่ให้รายการ Binance ถูกจับคู่กับสลิปธนาคารหรือกลับกัน
  2. จำกัดการส่งสลิปต่อผู้ใช้และจำนวนเรียก API; รับเฉพาะไฟล์ภาพจาก private chat ที่จำกัดขนาดและตรวจเนื้อหาไฟล์จริง ไม่เชื่อ MIME/นามสกุลอย่างเดียว; ไม่รับ URL จากผู้ใช้
  3. ส่ง API ผ่าน HTTPS พร้อม timeout; ตรวจ HTTP status และรูปแบบ response ตามสัญญา API; ไม่ค้าง transaction ฐานข้อมูลระหว่างรอ API และไม่บันทึกภาพ, API key หรือ response ที่มีข้อมูลอ่อนไหวลง log
  4. แยกการจับคู่ตาม provider; ห้ามเรียกใช้การ match Binance ปัจจุบันโดยตรง เพราะปัจจุบันจับคู่ด้วยยอด USDT เฉพาะและไม่ได้แยก provider/บัญชีธนาคาร
  5. ให้ SlipOK เป็นผู้ตรวจ และตรวจ success, สกุลเงิน, ยอดแบบ exact, บัญชีผู้รับที่ตั้งค่าไว้, transaction reference และ timestamp/ช่วงเวลาคำขอก่อนพิจารณาเครดิต; field ที่หายหรือกำกวมเข้าตรวจ manual
  6. ใช้ `log: true` เป็นชั้นตรวจซ้ำจาก SlipOK และเก็บ provider + transaction reference แบบ unique ในฐานข้อมูลของเราเอง; บันทึก payment, เปลี่ยนสถานะคำขอ และลง wallet ledger แบบ atomic/idempotent
  7. สลิปซ้ำ, ยอด/ผู้รับไม่ตรง, คำขอหมดอายุ/ยกเลิก, API timeout/ผลลัพธ์ไม่ทราบแน่ชัด/ผิดรูปแบบ หรือข้อมูลกำกวม ต้องไม่เติมเครดิตอัตโนมัติ; แจ้งผู้ใช้ให้ติดต่อส่วนตัวตามที่เจ้าของกำหนด โดยยังไม่เครดิต; หากแอดมินปรับเครดิตภายหลังให้บันทึกเหตุผลและหลักฐานใน audit
  8. เก็บ API key ใน environment ฝั่ง server เท่านั้น; ห้ามใส่ key ใน Telegram, log, source control หรือหน้าเว็บ
- กติกายอดเติมธนาคารที่ผู้ใช้ระบุ: ขั้นต่ำ 150 บาท และอัตราเริ่มต้น 1 credit = 34.50 บาท; แอดมินเปลี่ยนเรตผ่าน dashboard ได้ และคง Binance Pay ที่อัตรา 1 USDT = 1 credit แยกจากธนาคาร
- บัญชีรับเงินที่ผู้ใช้ให้: ตั้งชื่อบัญชีและเลขบัญชีใน `.env` (`BANK_ACCOUNT_NAME`, `BANK_ACCOUNT_NUMBER`) แล้วแสดงใน Telegram ก่อนโอน; ห้ามฝังข้อมูลบัญชีใน source, migration, tests หรือไฟล์ที่เผยแพร่
- อายุคำขอเติมผ่านธนาคาร: 15 นาทีจากเวลาสร้างคำขอ; หลังจากนั้นแสดงสถานะหมดเวลา/ล้มเหลวถ้ายังไม่มีการโอนที่ตรวจผ่าน และห้ามเครดิตรายการที่ SlipOK ยืนยันว่าโอนหลังเวลาหมดอายุ
- ใช้ `transTimestamp` ที่ SlipOK ส่งกลับเป็นเวลาธุรกรรม โดยตรวจว่าอยู่ระหว่างเวลาเริ่มคำขอกับเวลาหมดอายุ (รวมขอบเขตตามความละเอียด timestamp); ห้ามเชื่อเวลาจากข้อความ/มือถือของผู้ใช้ หากอัปโหลดสลิปช้ากว่า 15 นาทีแต่เวลาธุรกรรมอยู่ในหน้าต่าง ให้ตรวจต่อได้เพื่อไม่ปฏิเสธผู้ที่โอนทันเวลา ทั้งนี้ transRef ต้องยังไม่เคยใช้
- ข้อเสนอเรื่องยอด: ให้ผู้ใช้กรอกยอดเงินบาทตั้งแต่ 150 บาท แล้วระบบเพิ่มเศษสตางค์สุ่ม 0.01–0.99 บาทและแสดงยอดโอนสุทธิพร้อมเครดิตที่จะได้รับก่อนยืนยัน; คิดเครดิตจากยอดโอนสุทธิจริงหารด้วยเรตที่ตั้งอยู่ใน dashboard เพื่อไม่เก็บเศษเงินที่ผู้ใช้โอนโดยไม่ให้เครดิต
- ป้องกันยอดชน: สุ่มได้ไม่เกิน 99 ค่าในยอดฐานเดียว จึงต้องบังคับ unique ยอดโอนที่ยังใช้งานอยู่ต่อบัญชีรับเงินใน DB, retry เมื่อชน, จำกัดคำขอและอายุรายการ; เมื่อไม่มียอดว่างให้ขอให้ผู้ใช้เลือกยอดฐานใหม่แทนการ reuse
- ขั้นตอนก่อนเปิดใช้: เพิ่ม regression tests ก่อน implementation → เพิ่ม schema และ service/provider → เพิ่มเมนูธนาคาร/อัปโหลดสลิปและสถานะตรวจ → ทดสอบธุรกรรม/การแข่งขัน/ความล้มเหลว → code/security/database review → อัปเดตเอกสารและ CHANGELOG → deploy หลังตั้งค่า secret และทดสอบจริง
- กรณีทดสอบขั้นต่ำ: ผ่านปกติ, สลิปปลอม/ไม่ผ่าน, ผู้รับผิด, ยอดผิด, transRef ซ้ำ, ส่งซ้ำพร้อมกัน, โอนก่อนหมดเวลาแต่ตรวจหลังหมดเวลา, โอนหลัง 15 นาทีต้องล้มเหลว/ไม่เครดิต, ยกเลิกคำขอ, API ล่มหรือ response ผิดรูปแบบ, ยอดต่ำกว่า 150 บาทถูกปฏิเสธ, conversion/rounding ตามเรตใน dashboard และการชนของเศษสตางค์; ยืนยันว่า Binance เดิมยังทำงาน
- ต้องได้ข้อมูลก่อนทดสอบจริง: SlipOK API key และ branch ID (ป้อนบน VPS ผ่าน `.env`), ชื่อ/เลขบัญชีรับเงินและรูปแบบ receiver fields ที่ SlipOK ส่งกลับ, ข้อจำกัดแพ็กเกจ API และแนวทางเมื่อ API ใช้งานไม่ได้
- ข้อจำกัด: คู่มือ API ที่ผู้ใช้ให้มาระบุรูปแบบการตรวจสลิปและการเปิด `log: true` แต่ยังไม่ยืนยันแพ็กเกจ/วงเงิน/การรองรับบัญชีธนาคารของบัญชี SlipOK จริง; ต้องยืนยันกับผู้ให้บริการก่อนเปิดใช้จริง

## งานก่อน deploy: ตรวจระบบเติมเงินธนาคารและเวลาส่งอีเมล

- สถานะ: รีวิวจาก performance-optimizer, security-reviewer และ database-reviewer ใน `agents/` เสร็จ; ปรับจุดคอขวดความเสี่ยงต่ำและตรวจชุดทดสอบ/lint ผ่านแล้ว; ยังไม่ deploy
- ขอบเขต: ให้ผู้ตรวจด้านประสิทธิภาพวิเคราะห์เวลาตั้งแต่ซื้อจนส่งเมล, ให้ผู้ตรวจโค้ดและความปลอดภัยตรวจ diff งานเติมเงิน SlipOK ที่ยังไม่ deploy
- เงื่อนไข: ปรับความเร็วเฉพาะเมื่อไม่ลดการตรวจสลิป, idempotency, ledger/outbox correctness หรือความปลอดภัย; ถ้าประโยชน์ไม่ชัด/ต้องแลกความถูกต้องให้คงพฤติกรรมเดิม
- การตรวจ: เพิ่ม regression test ก่อนแก้, รันชุดทดสอบที่เกี่ยวข้องและ lint, สรุปข้อจำกัดก่อน deploy
- ผลตรวจเบื้องต้น: worker รอสูงสุด 2 วินาทีก่อนพบ outbox ใหม่ และ `purchase()` อ่านเนื้อหาเมลที่ Telegram ไม่ได้ใช้ก่อน worker อ่านซ้ำ; พิจารณาแล้วคงรอบตรวจคิว 2 วินาทีเพื่อลดคำขอ idle ไปยัง Supabase และให้ Telegram ข้ามเฉพาะการอ่านเนื้อหาเมลซ้ำ โดยคงการส่งแบบ outbox ทีละงาน
- ผลตรวจอัตโนมัติ: 201 tests ผ่าน, 7 PostgreSQL tests ข้ามเพราะไม่มี `TEST_DATABASE_URL`, Ruff และ compileall ผ่าน; ไม่มี timing measurement จาก VPS จริง จึงไม่ยืนยันตัวเลขเวลารวมที่ลดลง
- ข้อจำกัด: ยังไม่มี timing จาก VPS จริง; SlipOK branch ต้องผูกกับบัญชีผู้รับเดียวกับที่ตั้งไว้ใน `.env` ก่อนเปิดเติมเงินธนาคาร

## แผนงาน: จำกัดการตรวจสลิป SlipOK และป้องกันรูปซ้ำ

- สถานะ: implementation และ automated verification เสร็จ (2026-10-23); ยังไม่ deploy
- เป้าหมาย: จำกัดการเรียกตรวจ SlipOK ไม่เกิน 5 ครั้งต่อ Telegram ID ต่อวันปฏิทินไทย และไม่ส่งไฟล์ภาพที่มี SHA-256 ซ้ำเข้า SlipOK อีก
- ขอบเขต: บันทึกโควตา/แฮชในฐานข้อมูล เพื่อคงอยู่หลัง restart และทำงานได้หลาย process; ตรวจรูปแบบ/ขนาดภาพในเครื่องก่อนนับโควตา; นับความพยายามก่อนเรียก provider แบบ conservative เพื่อไม่ให้ retry หรือ crash เปิดช่องเกินโควตา
- ขั้นตอน/ผล: เพิ่ม tests สำหรับ cap 5, วันไทย/เปลี่ยนวัน, hash ซ้ำ, hash ผิดรูปแบบ, concurrency บน PostgreSQL และ local image validation → เพิ่มตารางบันทึก attempt พร้อม unique constraints และ atomic slot reservation; `team-mail init-db` สร้างตารางใหม่และตั้ง RLS/สิทธิ์ให้อัตโนมัติ → เชื่อม flow อัปโหลดภาพเข้ากับการตรวจ local validation, hash และ reserve ก่อนเรียก API → เพิ่มข้อความภาษาไทยเมื่อรูปซ้ำหรือครบโควตา → full suite และ lint ผ่าน
- ความเสี่ยง/แนวทาง: นับรูปที่จองโควตาแล้วแม้ process จะหยุดก่อนส่งจริง เป็นการนับเกินได้เล็กน้อยแต่ไม่เปิดช่องเรียกเกิน 5 ครั้ง; hash ตรงกันเฉพาะ bytes เดิม จึงยังมี SlipOK `log: true` และ transaction reference ในฐานข้อมูลเป็นการป้องกันซ้ำอีกชั้น
- เกณฑ์สำเร็จ: user หนึ่งคนมีได้สูงสุด 5 attempt ต่อวันไทยแม้เรียกพร้อมกัน; เริ่มนับใหม่เที่ยงคืนไทย; ไฟล์ hash เดิมไม่เรียก SlipOK ซ้ำแม้คนละผู้ใช้/คนละวัน; Binance flow ไม่เปลี่ยน
- ข้อจำกัดก่อน deploy: tests ผ่าน 210 รายการและข้าม 9 PostgreSQL integration tests เพราะไม่มี `TEST_DATABASE_URL`; manager update เรียก `team-mail init-db` เพื่อสร้างตารางใหม่ก่อน restart; ยังไม่ได้ deploy

## แผนงาน: เพิ่มหน้ารายงานสรุปยอดตามช่วงเวลา

- สถานะ: deploy แล้วผ่านเมนู update ของ `bot-manager.bat` เมื่อ 2026-10-24; migration สำเร็จ, bot/worker/web active และหน้า `/reports` ตอบกลับหน้า login ตามสิทธิ์แอดมิน; full suite ผ่าน 233 รายการ (9 PostgreSQL integration tests ข้ามเพราะไม่มี `TEST_DATABASE_URL`), coverage 90%, Ruff และ `git diff --check` ผ่าน
- เป้าหมาย: เพิ่มหน้าแอดมินสำหรับดูผลงานรายวันและยอดรวมตามช่วงวันที่ เลือกวันนี้, เมื่อวาน, 7 วัน, 30 วัน, ระบุวันเริ่ม/วันสิ้นสุดเอง หรือดู all time ได้
- แนวทางหน้าเว็บ: เพิ่มลิงก์ “รายงาน” และหน้าอ่านอย่างเดียวที่ `GET /reports`; แสดงการ์ดสรุปช่วงที่เลือกและตารางยอดรายวัน; all time แสดงยอดรวมพร้อมตารางรายวันแบบแบ่งหน้า/จำกัดจำนวนวัน เพื่อไม่ส่งผลลัพธ์จำนวนมากเกินจำเป็น
- นิยามตัวเลข:
  1. เมลที่ส่งสำเร็จและเครดิตขาย: นับจากออเดอร์ที่ส่งครบแล้วเท่านั้น; แสดงจำนวนเมล, เครดิตที่หัก, เครดิตคืน และยอดเครดิตสุทธิแยกกัน; ไม่นับ pending/failed และไม่ปนการปรับเครดิตโดยแอดมิน
  2. เงินรับจริงจากการเติม: แสดง THB จากรายการ `BankPayment` ที่ยืนยันสำเร็จ และ USDT จาก `Payment` ที่ยืนยันสำเร็จแยกคนละตัวเลข; แสดงเครดิตที่เข้ากระเป๋าจากแต่ละช่องทางแยกด้วย; ห้ามแปลงสองสกุลเป็นเงินบาทด้วยเรตปัจจุบันแล้วเรียกว่าเงินรับจริง
  3. หากเพิ่มตัวเลข “มูลค่าขายโดยประมาณ” ในอนาคต ต้องติดป้ายว่าเป็นประมาณการและใช้เรตที่บันทึกกับธุรกรรม ณ เวลานั้น; ไม่ใช้เรตปัจจุบันแทนประวัติ
- วันและช่วงเวลา: รับวันปฏิทินตาม Asia/Bangkok, ตรวจรูปแบบ/ลำดับ/ขอบเขตวันที่, ใช้ start-inclusive/end-exclusive โดยแปลงเที่ยงคืนไทยเป็น UTC ก่อน query; today เป็นค่าเริ่มต้น; all time ไม่ใส่ date predicate; คำขอ custom ต้องจำกัดจำนวนวันหรือแบ่งหน้าข้อมูลรายวัน
- ความถูกต้องของวันส่ง: เพิ่ม `orders.delivered_at` และกำหนดเวลาเมื่อออเดอร์เปลี่ยนเป็น delivered หลังส่งครบ; migration เติมค่าให้ประวัติ delivered เก่าจาก `created_at` เพื่อให้เปิดดู all time ได้ โดยระบุว่าแถวเก่าก่อน release เป็นวันที่สร้างออเดอร์โดยประมาณ ไม่ใช่เวลาส่งจริง
- ข้อมูลและประสิทธิภาพ: ทำ aggregate ในฐานข้อมูล แทนการโหลดออเดอร์/ธุรกรรมทั้งหมดเข้า Python; ใช้ `delivered_at` สำหรับยอดขายและ `occurred_at` สำหรับยอดรับเงิน; ตรวจ query plan และเพิ่ม migration/index เฉพาะที่จำเป็นสำหรับ `orders(delivered_at, status)` และ payment timestamp/status; แบ่งการ query รายวันตาม timezone ไทยอย่างสอดคล้องทั้ง PostgreSQL และ SQLite test backend
- ความปลอดภัย: ใช้ session admin gate เดิม, read-only endpoint, bind ค่าวันที่เป็น parameters, ไม่รับ SQL/order expression จากผู้ใช้ และไม่เปิดข้อมูลผู้ใช้/ธุรกรรมเกินความจำเป็น
- ขั้นตอน implementation: เขียนข้อกำหนด/สูตรและ regression tests ก่อน → เพิ่ม `delivered_at` + migration และตั้งค่าตอนส่งครบ → เพิ่ม aggregate service → เพิ่ม route validation และหน้า report/ตัวเลือกช่วงวัน → เพิ่มลิงก์นำทาง → รีวิว code/database/security → รันชุดทดสอบที่เกี่ยวข้อง, full suite, lint และตรวจ diff → อัปเดต CHANGELOG
- กรณีทดสอบหลัก: ขอบเขตเที่ยงคืนไทยและ UTC, today/ช่วงกำหนดเอง/all time, ช่วงกลับด้าน/อนาคต/รูปแบบผิด, zero-data, delivered เทียบกับ pending/refunded, นับจำนวนเมลและเครดิตคืน, THB กับ USDT ไม่รวมผิดสกุล, payment ซ้ำไม่ถูกนับซ้ำ, สิทธิ์ผู้ไม่ใช่แอดมิน, migration/backfill และ query จำนวนมาก
- ข้อควรระวัง: เงินที่เติมเข้ากระเป๋าไม่เท่ากับรายได้จากการขายโดยอัตโนมัติ และเครดิตที่ขายไม่ใช่เงินบาทที่รับจริง; UI ต้องใช้หัวข้อแยกกันเพื่อไม่ให้ตีความยอดผิด
