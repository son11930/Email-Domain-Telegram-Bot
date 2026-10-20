# ผลตรวจและสถานะส่งมอบ

วันที่: 2026-10-20 | โปรแกรมรุ่น 0.1.0

## ผลตรวจที่ทำจริง

- Python 3.14.5 บน Windows ใน virtual environment แยกของโปรเจค
- Automated tests **141 ผ่าน ไม่มีรายการข้าม** รวม PostgreSQL 17 จริงชั่วคราวที่ bind localhost เฉพาะข้อมูลทดสอบ
- PostgreSQL tests 6 รายการ: แย่งเมลสุดท้าย, callback ซ้ำพร้อมกัน, transaction เดียวกันซ้ำ, สองรายการรับเงินแข่งใช้ยอดเดียว, RLS/สิทธิ์ anon-authenticated และยกเลิกเติมพร้อมเงินเข้า
- Coverage รวม statement/branch **92.24%** ผ่านเกณฑ์ 80% ไฟล์รายงานสร้างเป็น coverage.xml (ไม่เก็บใน source control)
- End-to-end จำลองบริการภายนอก: ผู้ใช้ใหม่เข้า Telegram → เติมผ่าน signed API fixture → เครดิตครั้งเดียว → ซื้อหลายเมล → ส่ง TXT หนึ่งชุดและข้อความครบ → Discord สองห้อง → order delivered และ outbox ว่าง
- เว็บทดสอบ Auth protocol, anonymous/member authorization, CSRF, session/login limits, credit preview/stale balance, import ตัดรหัสผ่าน, ลบเดี่ยว/ชุด, ปรับราคา คืนเครดิต และตรวจเงินค้าง
- Ruff ผ่าน, pip check ไม่พบ dependency ขัดกัน, compileall ผ่าน
- pip-audit ไม่พบช่องโหว่ที่ทราบในแพ็กเกจที่ติดตั้ง หลังอัปเดต pip ภายใน virtual environment เป็น 26.2.1; local package ของเราไม่ได้อยู่ในฐาน PyPI จึงตรวจด้วย code/security review และ tests แทน
- สร้าง wheel สำเร็จและตรวจว่ามี templates/admin.html อยู่ใน package
- มีคำเตือน deprecation จาก Starlette TestClient/httpx หนึ่งรายการ ไม่ทำให้ tests ล้ม ไม่มีการซ่อนคำเตือนนั้น

## การตรวจโค้ดและแก้ไข

แก้จุดที่พบเกี่ยวกับการจองยอดทิ้ง, refund กับงานส่งค้าง, stale outbox lease, anonymous session exhaustion, synchronous auth ที่บล็อก async routes, การซ่อน secrets ใน provider traceback และ INSERT rowcount ที่ทำงานต่างกันบน psycopg จริง มี regression tests รองรับ

## ข้อที่ยังไม่ได้ตรวจด้วยบริการจริง

- ยังไม่มี Supabase project/credentials, Telegram token, Binance reader key/receiver และ Discord webhooks ของเจ้าของ จึงไม่ได้เรียกบัญชี production หรือส่งข้อความจริง
- ยังไม่ยืนยันว่าบัญชี Binance/เส้นทาง UID ของเจ้าของอ่านประวัติได้และโอนละเอียด 3–4 หลักได้จริง ต้องผ่าน smoke test ยอดเล็กก่อนเปิดรับเงิน
- ยังไม่เข้าถึง VPS จึงยังไม่ยืนยัน OS/Ubuntu ESM, firewall, outbound IP, DNS, HTTPS หรือ backup restore บนบริการจริง
- ยังไม่ได้ทดสอบติดตั้งบน VPS จริง; เพิ่ม systemd template ที่เปิด GNU Screen หลัง boot และตั้ง restart policy รวมทั้งย้ายเว็บแอดมินไป localhost:8001 แต่ต้องตรวจ unit/script และพอร์ตว่างบน Ubuntu จริงก่อนใช้งาน ส่วน Docker templates ที่คงไว้ไม่ได้ใช้เป็นเส้นทางติดตั้งหลักและไม่ได้ build/run ในเครื่องพัฒนา
- พยายามเปิด browser เพื่อตรวจภาพเว็บแล้ว แต่ Playwright extension ไม่พร้อม จึงไม่มีการยืนยันภาพหน้าจอด้วย browser; เส้นทางเว็บและ HTML ผ่าน automated TestClient และ core integration tests

## ข้อจำกัดการออกแบบที่ต้องรู้

- ยอดเฉพาะไม่ reuse เพื่อไม่จับเงินโอนเก่าเข้าคนใหม่ พื้นที่เศษจำกัด (99 ต่อฐานในโหมด 4 หลัก / 9 ในโหมด 3 หลักตามช่วงเศษปัจจุบัน) เมื่อหมดเลือกฐานอื่น เช่น 1.01 แทน 1.00 ห้ามลบ reservations เพื่อคืนช่องโดยไม่มีวิธีพิสูจน์ผู้จ่ายเพิ่ม
- จำกัดคำขอที่ยังไม่เครดิต 3 ครั้งต่อ rolling 24 ชั่วโมง และเว้น 60 วินาที ลดการจองทิ้ง แต่ไม่ป้องกันการใช้หลาย Telegram accounts ได้ทั้งหมด
- Telegram/Discord อาจรับข้อความแล้วตอบ timeout จึงอาจมีข้อความเดิมซ้ำ แต่การจัดสรรเมลและเครดิตต้องไม่ซ้ำ งาน retry ใช้ order เดิม
- คืนเครดิตยกเลิกงานส่งที่ยังค้าง แต่ไม่เรียกคืนข้อความที่ส่งแล้วหรือหยุด network request ที่อยู่ระหว่างส่งได้
- init-db เป็น baseline สร้างตาราง ไม่ใช่ schema upgrade engine รุ่นที่เปลี่ยน schema ต้องเพิ่ม migration
- บอท polling หนึ่ง instance และเว็บหนึ่ง worker เนื่องจาก session/UI state ใน memory; ledger/orders/outbox/checkpoints อยู่ PostgreSQL ถาวร

## เริ่มใช้งานจริง

สร้าง `.env` ตามตัวแปรที่ระบุใน [SETUP.md](SETUP.md) แล้วตรวจรายการก่อนเปิดใช้งานใน [OPERATIONS.md](OPERATIONS.md) ห้ามเปิดรับเงินจริงจนผ่านเงื่อนไขบัญชี Binance และการกระทบยอดจริง
