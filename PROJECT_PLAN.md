# Project Plan

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
- กติกายอดเติมธนาคารที่ผู้ใช้ระบุ: ขั้นต่ำ 150 บาท และอัตรา 1 credit = 33.50 บาท; คง Binance Pay ที่อัตรา 1 USDT = 1 credit แยกจากธนาคาร
- บัญชีรับเงินที่ผู้ใช้ให้: ตั้งชื่อบัญชีและเลขบัญชีใน `.env` (`BANK_ACCOUNT_NAME`, `BANK_ACCOUNT_NUMBER`) แล้วแสดงใน Telegram ก่อนโอน; ห้ามฝังข้อมูลบัญชีใน source, migration, tests หรือไฟล์ที่เผยแพร่
- อายุคำขอเติมผ่านธนาคาร: 15 นาทีจากเวลาสร้างคำขอ; หลังจากนั้นแสดงสถานะหมดเวลา/ล้มเหลวถ้ายังไม่มีการโอนที่ตรวจผ่าน และห้ามเครดิตรายการที่ SlipOK ยืนยันว่าโอนหลังเวลาหมดอายุ
- ใช้ `transTimestamp` ที่ SlipOK ส่งกลับเป็นเวลาธุรกรรม โดยตรวจว่าอยู่ระหว่างเวลาเริ่มคำขอกับเวลาหมดอายุ (รวมขอบเขตตามความละเอียด timestamp); ห้ามเชื่อเวลาจากข้อความ/มือถือของผู้ใช้ หากอัปโหลดสลิปช้ากว่า 15 นาทีแต่เวลาธุรกรรมอยู่ในหน้าต่าง ให้ตรวจต่อได้เพื่อไม่ปฏิเสธผู้ที่โอนทันเวลา ทั้งนี้ transRef ต้องยังไม่เคยใช้
- ข้อเสนอเรื่องยอด: ให้ผู้ใช้กรอกยอดเงินบาทตั้งแต่ 150 บาท แล้วระบบเพิ่มเศษสตางค์สุ่ม 0.01–0.99 บาทและแสดงยอดโอนสุทธิพร้อมเครดิตที่จะได้รับก่อนยืนยัน; คิดเครดิตจากยอดโอนสุทธิจริงหาร 33.50 เพื่อไม่เก็บเศษเงินที่ผู้ใช้โอนโดยไม่ให้เครดิต
- ป้องกันยอดชน: สุ่มได้ไม่เกิน 99 ค่าในยอดฐานเดียว จึงต้องบังคับ unique ยอดโอนที่ยังใช้งานอยู่ต่อบัญชีรับเงินใน DB, retry เมื่อชน, จำกัดคำขอและอายุรายการ; เมื่อไม่มียอดว่างให้ขอให้ผู้ใช้เลือกยอดฐานใหม่แทนการ reuse
- ขั้นตอนก่อนเปิดใช้: เพิ่ม regression tests ก่อน implementation → เพิ่ม schema และ service/provider → เพิ่มเมนูธนาคาร/อัปโหลดสลิปและสถานะตรวจ → ทดสอบธุรกรรม/การแข่งขัน/ความล้มเหลว → code/security/database review → อัปเดตเอกสารและ CHANGELOG → deploy หลังตั้งค่า secret และทดสอบจริง
- กรณีทดสอบขั้นต่ำ: ผ่านปกติ, สลิปปลอม/ไม่ผ่าน, ผู้รับผิด, ยอดผิด, transRef ซ้ำ, ส่งซ้ำพร้อมกัน, โอนก่อนหมดเวลาแต่ตรวจหลังหมดเวลา, โอนหลัง 15 นาทีต้องล้มเหลว/ไม่เครดิต, ยกเลิกคำขอ, API ล่มหรือ response ผิดรูปแบบ, ยอดต่ำกว่า 150 บาทถูกปฏิเสธ, conversion/rounding ที่ 33.50 บาทต่อ credit และการชนของเศษสตางค์; ยืนยันว่า Binance เดิมยังทำงาน
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
