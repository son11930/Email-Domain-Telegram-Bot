# ดูแลระบบและแก้ปัญหา

## งานประจำ

ดูสถานะด้วย `sudo systemctl status team-mail@bot.service team-mail@worker.service team-mail@web.service` และ `sudo -u team-mail screen -ls` ดู log เช่น `sudo tail -n 100 /opt/team-mail-bot/logs/worker.log` โดย logrotate เก็บรายวัน 7 ชุด ลบ key/token/email ส่วนตัวก่อนแชร์ log ให้ผู้อื่น ห้ามแสดง `.env` หรือ connection URL systemd เปิดบริการหลัง reboot และ restart session ที่จบเอง; ตรวจเหตุขัดข้องด้วย `sudo journalctl -u team-mail@worker.service -n 100 --no-pager`

## เข้าเว็บแอดมินจาก public IP

เปิด `https://45.136.254.62/login` เว็บแอปยัง bind เฉพาะ `127.0.0.1:8001`; Nginx รับการเชื่อมต่อภายนอกบนพอร์ต 80/443 และส่งต่อ HTTPS ไปยังเว็บ พอร์ต 80 เปลี่ยนเส้นทางไป HTTPS อัตโนมัติ ล็อกอินด้วยบัญชี Supabase Auth ที่ UUID อยู่ใน `WEB_ADMIN_SUBJECTS`

ใบรับรองเป็น Let's Encrypt short-lived IP certificate และมีอายุประมาณ 6 วัน Certbot Snap timer ต่ออายุอัตโนมัติวันละสองครั้ง และ deploy hook reload Nginx เมื่อได้ใบรับรองใหม่ อย่าปิด `snap.certbot.renew.timer` หรือบล็อก outbound ACME/HTTP challenge traffic ตรวจ timer ด้วย `systemctl status snap.certbot.renew.timer` และดูวันหมดอายุด้วย `sudo certbot certificates` หาก renewal ล้มเหลว ให้ตรวจ `journalctl -u snap.certbot.renew.service` และทดสอบ `sudo certbot renew --cert-name team-mail-admin-ip --dry-run`

อย่าเปิดพอร์ต 8001 สู่ public internet และอย่าใช้ HTTP ตรงกับหน้า login พอร์ต 8000 เป็นของ service อื่นและห้ามเปลี่ยน

อัปเดตจาก Windows ผ่าน `bot-manager.bat` เมนู 5 จะ fast-forward pull `main`, ติดตั้ง dependencies ตาม lockfile, ติดตั้งโปรเจกต์, รัน `init-db` และ restart bot/worker/web; เมนู 2 เริ่ม service ทั้งสาม ส่วน systemd units ที่ enable ไว้จะเริ่มเองหลัง reboot ตัว manager ใช้ `%USERPROFILE%\.ssh\known_hosts` และบังคับ `StrictHostKeyChecking=yes`; ถ้าเรียกจาก runtime ที่มี Windows profile คนละตัว ให้ตั้ง `TEAM_MAIL_SSH_KNOWN_HOSTS` เป็น path ของ known_hosts ที่ตรวจสอบแล้วก่อนเปิด manager

Bot รับคำสั่ง Telegram, worker อ่าน Binance และส่ง outbox, web ให้แอดมินทำรายการ ใช้ PostgreSQL เดียวกัน ความสำเร็จของธุรกรรมอยู่ที่ DB งานส่งอาจตามมาภายหลัง หาก Telegram timeout อาจเกิดข้อความซ้ำ แต่การซื้อ/เครดิตต้องอ้างรายการเดิม

รันแต่ละบริการอย่างละหนึ่ง instance โดย bot และ web ใช้สถานะสนทนา/session ในหน่วยความจำ จึงห้าม scale เพิ่มโดยยังไม่เปลี่ยนระบบเก็บสถานะ หลัง restart ให้ผู้ใช้เริ่มขั้นตอนที่ค้างใหม่หรือให้แอดมินล็อกอินใหม่ Worker มี claim token และกู้คืนงานได้ รุ่นปัจจุบันประมวลผลงานที่ claim ทีละงาน อย่าเพิ่ม worker เพื่อเร่งส่งโดยไม่ประเมิน rate limit และการทำงานพร้อมกัน

## ปรับเครดิตและนำเข้าเมล

1. ให้สมาชิก `/start` ก่อน แล้วค้นด้วย numeric Telegram ID บนเว็บ admin ตรวจชื่อประกอบ
2. ปรับเครดิตผ่านหน้าจอ admin ระบุเหตุผล ตรวจยอดเดิมและยอดใหม่ก่อนยืนยัน ให้ระบบเขียน ledger คู่กับยอด ห้ามแก้ `users.balance_units` ตรงผ่าน Table Editor
3. นำเข้าอีเมลล้วนหรือข้อมูล `เลขลำดับ email|password` ผ่านช่องเพิ่มเมล/ไฟล์ `.txt` UTF-8 ดู preview ก่อนยืนยัน แนะนำเมลล้วนเพื่อลดข้อมูลลับในข้อความต้นทาง
4. อีเมลโดเมนหลายระดับใช้ได้ ไม่บังคับ Gmail ไม่ต่ออีเมลที่ขาดกลางบรรทัดจากภาพโดยเดา
5. ลบเฉพาะเมลพร้อมขาย เมลขายแล้วต้องเก็บกับ order/history ห้ามปล่อยกลับคลังเพราะส่งข้อความไม่สำเร็จเพียงอย่างเดียว

Supabase Table Editor เหมาะสำหรับดูและตรวจข้อมูลหรือแก้ฉุกเฉินที่เข้าใจผลกระทบ งานประจำใช้เว็บ/Telegram admin เพื่อให้มี audit และคงยอดตรง ledger จำนวนเงินเก็บหน่วยย่อย 100,000,000 หน่วยต่อ 1 credit ห้ามใช้ float แปลงยอด

ใน Telegram เลือก **จัดการสำหรับแอดมิน → ปรับเครดิต** แล้วส่ง `TELEGRAM_ID จำนวน` เช่น `6450298295 1.5` เพื่อเพิ่ม 1.5 credit หรือ `6450298295 -1.5` เพื่อลด 1.5 credit หรือส่ง ID ก่อนแล้วค่อยส่งจำนวนเมื่อบอทถาม ระบบแสดงยอดเดิม/ยอดใหม่และต้องกดยืนยันก่อนบันทึก พร้อมใส่เหตุผลมาตรฐานใน audit อัตโนมัติ ปุ่ม **เพิ่มเมล** รับข้อความหรือ `.txt` ส่วน **ลบเมล** รับ `EMAIL_ID เหตุผล` โดยใช้รหัสรายการจากคลัง `/cancel` กลับเมนูและยกเลิกขั้นตอนที่ค้าง

เว็บหน้า **เครดิต** ค้นผู้ใช้และมีแบบฟอร์มปรับยอด หน้า **คลังอีเมล** นำเข้า/ลบเมล และหน้า **ราคา / ตรวจรายการ** ตั้งราคา คืนเครดิต order หรือตรวจเงินเข้าที่ต้องทบทวน การคืนเครดิตไม่คืนเมลที่เคยเปิดเผยเข้าคลัง ระบบยกเลิกส่วนส่งที่ยังค้างในคิว แต่คำขอเครือข่ายที่เริ่มส่งแล้วอาจไปถึงผู้ใช้ภายหลังได้ จึงไม่รับรองว่าเรียกเมลคืนหรือยับยั้งข้อความที่กำลังส่งได้

## เงินเข้าหาย/ไม่เครดิต

- ตรวจสถานะ DB ว่าถูก pause หรือเต็ม quota และ worker ทำงานหรือไม่
- ตรวจบัญชีรับ สกุล USDT ยอดทุกทศนิยม และเวลาธุรกรรมจาก Binance ไม่ใช้เวลาที่เห็นรูปสลิป
- คำขอหมดอายุ/ยกเลิกยังเก็บประวัติยอดเฉพาะ ห้ามลบเพื่อปล่อยยอดกลับมาใช้
- ตรวจ payment event ว่า match / unmatched / needs_review และ transaction ID ถูกใช้แล้วหรือไม่ การแก้ exception ต้องอ้างธุรกรรมรับจริงที่ owner ตรวจได้และบันทึกเหตุผล ห้ามเครดิตสองครั้งเพราะผู้ใช้ส่งเลขรายการซ้ำ
- หาก API มี permission/time error ตรวจ NTP / key / IP whitelist ห้ามเพิ่มสิทธิ์ถอนหรือ transfer
- หากช่วง API ขาดหายยาวเกิน lookback ให้ owner ตรวจประวัติช่วงที่หายและกระทบยอดก่อนรับรายการใหม่ การ restart อย่างเดียวไม่ยืนยันว่ากู้ประวัติครบ

ยอดเฉพาะไม่ reuse ตลอดอายุฐานข้อมูล ภายใต้ receiver เดิม ห้ามลบ amount leases/payment history เพื่อเพิ่มช่อง ยอดโอนหลังหมดอายุหรือผิดยอดเข้ากระบวนการตรวจสอบ ไม่ใช้เดาเจ้าของจากชื่อ

โหมด 4 หลักมี 99 ช่อง/ยอดฐาน และ 3 หลักมี 9 ช่อง/ยอดฐาน หากเต็มให้เลือกฐานอื่น เช่น 1.01 หรือให้แอดมินตรวจ รายการ pending จำกัดหนึ่งรายการต่อผู้ใช้ ขอใหม่ห่างอย่างน้อย 60 วินาที และจำกัดรายการยังไม่เครดิต 3 รายการในช่วง 24 ชั่วโมงย้อนหลัง (ไม่นับ paid) ข้อจำกัดนี้ป้องกันการใช้หลายบัญชีจองช่องทั้งหมดไม่ได้ ต้องเฝ้าดูการใช้งานผิดปกติ

## Telegram/Discord ส่งไม่สำเร็จ

ตรวจ outbox และ last error ผู้ใช้ต้องเริ่มแชทและไม่ block bot งานหลัง commit retry ต้องใช้ order เดิม ถ้าส่งถึงบางส่วนแล้วห้ามซื้อใหม่เพื่อส่งส่วนที่ขาด หาก API timeout อาจมีข้อความซ้ำได้ รหัส order ช่วยเทียบรายการเดิม

Discord order จะแจ้ง success หลังส่งอีเมลครบ และแจ้งไม่สำเร็จเมื่อมีการคืนเครดิต/ยกเลิกรายการ; ข้อผิดพลาดส่ง Telegram/Discord ชั่วคราวจะ retry จึงยังไม่ถือเป็นผลล้มเหลวถาวร Discord ตอบ 429 ให้ worker เคารพ retry-after ถ้า webhook ถูกลบให้สร้างใหม่ในห้องเดิม เปลี่ยน env แล้ว restart unit ที่เกี่ยวข้องด้วย `sudo systemctl restart team-mail@worker.service` ไม่ควรคืนเครดิตเพียงเพราะ notification ส่งไม่ได้

## Backup และกู้คืน

Supabase Free ไม่มี automatic backup รวมในแผน ให้ทำ logical backup ตาม [คู่มือ Supabase](https://supabase.com/docs/guides/platform/migrating-within-supabase/backup-restore) ก่อนอัปเกรดและเป็นประจำ เก็บเข้ารหัสนอก VPS ตรวจอายุไฟล์และซ้อม restore ไป project ทดสอบ อย่า dump auth schema ของ provider โดยไม่อ่านข้อจำกัดของ Supabase

ใช้ PostgreSQL client เวอร์ชันที่เข้ากันกับ server และ session pooler/direct connection ตาม provider ไม่ใช้ transaction pooler สำหรับ dump ตั้ง host/user/database แยก environment และใช้ `PGPASSFILE` ที่สิทธิ์ 600 แทนใส่รหัสผ่านใน command line ตัวอย่างเมื่อเตรียมค่า `PGHOST`, `PGPORT`, `PGUSER`, `PGDATABASE`, `PGSSLMODE=require`, `PGPASSFILE` แล้ว:

```sh
umask 077
pg_dump --format=custom --schema=public --no-owner --no-acl --file=team-mail.backup
```

ไฟล์นี้มีอีเมล/ประวัติการเงิน ต้องจำกัดสิทธิ์และเข้ารหัส ไม่รวม `.env` ในพื้นที่สาธารณะ การ restore ทดสอบใช้ DB ใหม่เท่านั้น:

```sh
pg_restore --no-owner --no-acl --exit-on-error --dbname=postgres team-mail.backup
```

ให้ environment ชี้ DB กู้คืนที่แยกแล้ว ตรวจ users/ledger/order_items/payment_events/amount_leases/outbox ครบและยอดตรงกันก่อนสลับ production Backup เฉพาะ public schema ไม่ได้สำรองบัญชี Supabase Auth หรือการตั้งค่า project ให้สร้าง admin Auth และตรวจ UUID ที่อนุญาตอีกครั้งเมื่อย้าย project ห้ามเปิด worker ของฐานทดสอบพร้อม production ด้วย Binance receiver/token/webhooks จริง เพราะอาจส่งข้อความและอ่านธุรกรรมซ้ำ

## อัปเดตและย้อนกลับ

สำรอง DB และบันทึก release ปัจจุบัน หยุดสาม unit ด้วย `sudo systemctl stop team-mail@bot.service team-mail@worker.service team-mail@web.service` นำ source รุ่นใหม่ลง working directory เดิมและติดตั้ง dependency ตาม release ด้วยบัญชี `team-mail` หากมี migration ระบุใน release ให้ใช้ SQL Editor ของ Supabase หรือ `psql` ต่อฐานที่ถูกต้องและทำ migration ก่อนรัน `.venv/bin/team-mail init-db` (ถ้า release ระบุ) แล้วเริ่มอีกครั้งด้วย `sudo systemctl start team-mail@bot.service team-mail@worker.service team-mail@web.service` ตรวจสถานะ, Screen sessions, log และธุรกรรมทดสอบ `init-db` สร้างตารางเริ่มต้นที่ยังไม่มีและตั้ง RLS; รุ่นนี้เพิ่ม `orders.delivered_at` แบบ idempotent และ backfill รายการที่ส่งแล้วจาก `created_at` เป็นค่าประมาณ พร้อมสร้าง indexes ของรายงาน ส่วน schema changes อื่นต้องมี migration ตาม release

ถ้า schema เปลี่ยนอย่าย้อนโค้ดเก่าโดยไม่ตรวจความเข้ากัน การ restore backup production จะทำให้ธุรกรรมหลัง backup หาย ต้องหยุดรับเงิน/ซื้อและกระทบยอด Binance ก่อน ห้ามถือว่าการ restore ทำให้การโอนเงินจริงย้อนกลับ

## เปลี่ยนสิทธิ์และหมุน secrets

เพิ่ม/ถอน Telegram admin ผ่าน `ADMIN_IDS` และ web admin UUID ผ่าน `WEB_ADMIN_SUBJECTS` บน VPS แล้ว restart ทั้งสาม unit เพื่อโหลดค่าใหม่ อย่าใช้ username แทน ID ตรวจถอนสิทธิ์ด้วยบัญชีเดิมหลังเปลี่ยน

หาก token/secret รั่ว ให้ revoke ที่ provider สร้างใหม่ อัปเดต `.env` และ restart units ทั้งหมด หมุน `SESSION_SECRET` เพื่อยกเลิก session เดิม ห้ามคัดลอก secret ไป Discord หาก Binance key รั่วหยุด worker ระหว่างเปลี่ยนและตรวจประวัติบัญชีรับย้อนหลัง

## ก่อนถือว่าพร้อมใช้งาน

ตรวจผล tests จริงของรุ่นนั้นและ PostgreSQL integration, HTTPS, สิทธิ์ anonymous/ผู้ใช้ทั่วไป/แอดมิน, backup restore, การกดซื้อซ้ำ, เงินไม่พอ, สต็อกไม่พอ, เติมซ้ำ, downtime worker, และธุรกรรม Binance จริงที่เจ้าของอนุญาต ต้องระบุผลที่ยังไม่ได้ทดสอบตามจริง ไม่ถือว่าการมีไฟล์ deploy คือ deploy สำเร็จ
