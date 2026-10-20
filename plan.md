# แผนบอท Telegram สำหรับซื้อและเบิกอีเมล

ปรับปรุง: 2026-10-20 | ฉบับ 2 พร้อมบันทึกผลพัฒนา | สถานะ: โค้ดและทดสอบในเครื่องเสร็จ รอตั้งค่าบริการจริง

## 1. ข้อกำหนดที่ยืนยันแล้ว

| หัวข้อ | ข้อกำหนด |
|---|---|
| ผู้ใช้งาน | ใครทักบอทก็เริ่มใช้ได้ทันที ไม่ต้องอนุมัติสมาชิก |
| สิทธิ์สำคัญ | เฉพาะแอดมิน: ปรับเครดิต เพิ่ม/ลบเมล ตั้งราคา และแก้รายการผิดปกติ |
| สินค้า | อีเมลโดเมนทั่วไป ประเภทเดียว ส่วนใหญ่ไม่ใช่ Gmail |
| ราคา | 0.30 USDT หรือ 0.30 credit ต่อเมล |
| อัตราเครดิต | 1 USDT = 1 credit |
| ซื้อด่วน | ปุ่มขอ 1 เมล กดครั้งเดียวหัก 0.30 credit และส่งเมล |
| ซื้อหลายเมล | ส่ง .txt หนึ่งไฟล์ที่มีเมลครบ และส่งเมลครบทุกอันเป็นข้อความคัดลอกได้ด้วย |
| เติมเงิน | Binance UID อัตโนมัติ จับคู่ด้วยยอดสุ่มทศนิยม 3–4 หลักตามภาพล่าสุด |
| ฐานข้อมูล | ฟรี อยู่นอก VPS; เสนอ Supabase Free (PostgreSQL) เป็นตัวเลือกหลัก |
| เว็บแอดมิน | ปรับเครดิต เพิ่ม/ลบเมล และดูประวัติ ใช้ควบคู่ Telegram |
| Discord | Webhook 2 ห้อง แยกเติมเงินสำเร็จและซื้อเมล |
| เครื่องรัน | VPS เดิม น่าจะ Ubuntu 20, CPU 2 core, RAM 4 GB ตามข้อมูลเจ้าของ ต้องตรวจจริง |

ภาพเดิมใช้เป็นแนวทางเมนู ไม่ต้องจำลองร้านต้นแบบทุกอย่าง ภาพล่าสุดอ้างอิงการเติมยอดเฉพาะ ไม่ถือ UID ในภาพเป็น UID ของเจ้าของ ข้อมูลตัวอย่างในเอกสารเป็นข้อมูลสมมติ บอทเก็บเฉพาะอีเมล ไม่เก็บรหัสผ่าน ไม่สร้างบัญชี ไม่อ่านกล่องเมลหรือ OTP

หลังตรวจฉบับ 2 เจ้าของอนุมัติให้พัฒนาแล้ว ปัจจุบันมี implementation และ automated tests โดยยังไม่มี credentials บริการจริง ไม่มีการโอนเงินจริงหรือ deploy โครงโปรเจคก่อนเริ่มงานมีเฉพาะชุด ECC

## 2. เมนูและสิทธิ์

ใคร /start ในแชทส่วนตัวก็สร้างบัญชีด้วย Telegram numeric user ID อัตโนมัติ ยอดเริ่มต้น 0 credit ไม่มี allowlist สมาชิกและไม่มีขั้นอนุมัติสมัคร

| เมนูสมาชิก | พฤติกรรม |
|---|---|
| ⚡ ขอ 1 เมลด่วน — 0.30 credit | ซื้อทันที ไม่มีหน้ายืนยันเพิ่ม |
| 📩 ซื้อหลายเมล | ระบุจำนวน → แสดงจำนวน × 0.30 และยอดหลังหัก → ยืนยัน |
| 💰 เติมเครดิต | เลือก 1/5/10/20 USDT หรือระบุยอด → รับยอดเฉพาะและ UID → ระบบตรวจเอง |
| 💳 ยอดคงเหลือ | แสดงยอดละเอียดและจำนวนเมลที่ซื้อได้ ไม่ปัดจนดูเหมือนซื้อได้ทั้งที่ยอดไม่พอ |
| 📦 คลังเมล | แสดงเฉพาะจำนวนพร้อมซื้อ ไม่เปิดรายการทั้งหมด |
| 📋 ประวัติ | การเติม/ซื้อ/ปรับยอดของตัวเอง และขอส่งเมลจากรายการซื้อเดิมอีกครั้ง |

แอดมินมีเมนูนำเข้า/เพิ่มเมล ลบเมลพร้อมขาย ปรับเครดิต ตั้งราคา และตรวจรายการผิดปกติ ส่วน owner จัดการรายชื่อแอดมิน สิทธิ์ใช้ ID ที่เชื่อถือได้ ไม่ใช้ username การซ่อนปุ่มไม่แทนการตรวจสิทธิ์ใน handler/callback/API

เปิดบอทให้ทุกคนใช้ พร้อม rate limit ป้องกัน spam และแยกข้อมูลผู้ใช้ คนหนึ่งดูหรือเรียกส่ง order ของอีกคนไม่ได้ สิทธิ์เว็บแอดมินมาจาก backend ที่ owner จัดการ ผู้ใช้ Telegram ไม่มีสิทธิ์เว็บแอดมินอัตโนมัติ ห้ามให้ใส่ Telegram ID แล้วรับสิทธิ์เอง

## 3. ซื้อเมลด่วนและหลายเมล

### ซื้อด่วน

1. แสดงราคา 0.30 credit รับ nonce ใช้ครั้งเดียวที่ผูกกับ user ID และเวอร์ชันราคา
2. ใน PostgreSQL transaction เดียว: ตรวจคำขอซ้ำ ล็อกยอดผู้ใช้ ตรวจเครดิต เลือก/ล็อกเมลพร้อมขาย หัก 0.30 สร้าง order/items/ledger และงานส่ง
3. Commit แล้วส่งเมลเป็นข้อความคัดลอกง่าย พร้อมเลขรายการ ยอดหักและยอดเหลือ
4. สร้างปุ่ม nonce ใหม่หลังสำเร็จ ปุ่มเก่าอ้างรายการเดิม กดซ้ำหรือ Telegram retry ไม่ซื้อ/หักเพิ่ม
5. เครดิตไม่พอ สต็อกหมด หรือราคาเปลี่ยน ไม่หักเงิน แจ้งเหตุและแสดงราคาใหม่เมื่อจำเป็น

### ซื้อหลายเมล

- จำนวนเป็นจำนวนเต็มบวก มีเพดานต่อ order ที่ตั้งค่าได้ ยืนยันก่อนซื้อ และตรวจขนาดไฟล์/จำนวนข้อความก่อนรับคำขอ
- ต้องมีเมลครบจำนวนและเงินพอ มิฉะนั้นไม่หักบางส่วน ล็อกราคาต่อหน่วยใน order เช่น 5 เมล = 1.50 credit
- ส่ง .txt UTF-8 หนึ่งไฟล์ต่อรายการในรอบส่งปกติ มีเมลครบหนึ่งเมลต่อบรรทัด ไม่มีเลขลำดับหรือรหัสผ่าน
- ส่งเมลชุดเดียวกันครบทั้งหมดเป็นข้อความ Telegram อีกทางหนึ่ง หากยาวให้แบ่งหลายข้อความตาม API limit โดยไม่ตัดกลางอีเมล (sendMessage สูงสุด 4,096 ตัวอักษรหลัง parse entities)
- ปิด parse mode หรือ escape ให้ถูกต้อง คงรูปแบบหนึ่งอีเมลต่อบรรทัดให้กดคัดลอกง่าย
- แยกสถานะส่งไฟล์/ข้อความแต่ละส่วน ถ้าพลาดให้ retry จาก order เดิมเฉพาะส่วนค้าง ไม่หยิบเมลหรือหักเงินใหม่
- ผู้ใช้ขอส่งใหม่จากประวัติได้ทั้งไฟล์/ข้อความรายการเดิมโดยไม่หักเครดิตเพิ่ม

### ความถูกต้องและการส่งล้มเหลว

- อีเมลแต่ละรายการจัดสรรให้ order ได้ครั้งเดียว ใช้ unique constraints/row locks ไม่ใช้ shared state ในหน่วยความจำเป็นหลักประกัน
- ใช้ outbox ใน DB เก็บงานส่ง Telegram/Discord เพื่อ restart แล้วทำต่อได้
- ล้มก่อน commit ต้อง rollback ทั้งยอดและเมล ล้มหลัง commit ให้ส่งรายการเดิมที่บันทึกแล้ว
- Timeout อาจหมายถึงส่งถึงแล้ว จึงอาจมีข้อความเดิมซ้ำ แต่เครดิตและการจัดสรรต้องไม่ซ้ำ
- ไม่คืนเครดิตหรือปล่อยเมลกลับคลังอัตโนมัติเมื่อผลส่งกำกวม การคืนต้องมี admin audit และทำครั้งเดียว เมลที่อาจเปิดเผยแล้วไม่กลับมาขาย

## 4. เพิ่ม/ลบอีเมลเฉพาะแอดมิน

รับข้อความหรือ .txt UTF-8 ผ่าน Telegram และเว็บ รองรับอีเมลล้วนแบบตัวอย่างที่เจ้าของแยกสำเร็จ และข้อมูลลำดับ + email|password จากภาพเดิม ต้องรองรับโดเมนหลายระดับ ไม่บังคับ @gmail.com

ตัวอย่างสมมติ:

```text
1.
member01@sub.example.org|<password>
2. member02@example.net|<password>
member03@sub.example.com
```

ผลลัพธ์เก็บและแจกเฉพาะ:

```text
member01@sub.example.org
member02@example.net
member03@sub.example.com
```

- ตัดเลขลำดับ/บรรทัดเลข อ่านอีเมลเฉพาะด้านซ้าย | ไม่ค้นหาอีเมลในรหัสผ่าน
- ตรวจรูปแบบและขนาดข้อมูล จำกัดไฟล์/จำนวนรายการ มี preview จำนวนผ่าน/ซ้ำ/ผิดก่อนยืนยัน ไม่สะท้อนรหัสผ่านกลับไป
- ไม่ทำ OCR รุ่นแรก ถ้าไฟล์มี newline กลางอีเมลให้แจ้งแก้ ไม่เดาต่อบรรทัด
- ไม่เก็บ raw input/password ใน DB, log, error monitoring หรือไฟล์ชั่วคราว ข้อความต้นทาง Telegram ยังเป็นข้อมูลของอีกระบบหนึ่ง แนะนำส่งอีเมลล้วนเมื่อทำได้
- กำหนด dedup: domain ไม่แยกตัวพิมพ์, local part คงเดิม ไม่ใช้กฎ Gmail ตัดจุด/+tag กับโดเมนทั่วไป
- ตรวจซ้ำทั้ง batch และประวัติทั้งหมด รวมขายแล้วและลบแล้ว เพื่อไม่ขายเมลเดิมซ้ำ
- ลบเมลพร้อมขายด้วย soft delete และบันทึก actor/เหตุผล ถ้าแข่งกับซื้อให้ transaction ตัดสิน ห้ามลบข้อมูลจัดสรรแล้วจนประวัติขาด
- ประเภทเดียว ใช้คลังเดียว ไม่ต้องมีหลายหมวดหมู่

## 5. เครดิตและการแก้ยอด

- ราคาเริ่มต้น 0.30 credit/เมล; 1 USDT = 1 credit คงที่ ไม่แปลงอัตราแลก USD/THB
- ข้อเสนอเรื่องเศษสุ่ม: เพิ่มเครดิตเท่า USDT รับจริง เช่น 5.0047 USDT ได้ 5.0047 credit เพื่อคงอัตรา 1:1 ไม่มีค่าธรรมเนียมเศษซ่อนอยู่
- เก็บจำนวนเป็น integer หน่วยย่อย 1 USDT = 100,000,000 units ใช้ Decimal แปลง ห้าม float เทียบยอดตามค่าจริง เช่น 1.230 = 1.2300
- Ledger แบบเพิ่มรายการใหม่มี delta ยอดก่อน/หลัง actor reason เวลา และ unique reference ครอบคลุมซื้อ เติม คืน ปรับยอด
- แอดมินบน Telegram/เว็บเลือกบัญชีด้วย ID เห็นชื่อประกอบ → เพิ่ม/ลดหรือระบุยอดเป้าหมาย → ดูยอดเดิม/ใหม่ → ยืนยันพร้อมเหตุผล
- ยอดเป้าหมายเทียบยอดล่าสุดใน transaction ไม่ให้หน้าเว็บเก่าทับผลซื้อ หากยอดเปลี่ยนระหว่าง preview ให้ยืนยันใหม่ ยอดห้ามติดลบ
- ราคาเปลี่ยนใช้กับ order ใหม่ ไม่แก้ประวัติเก่า เว็บกับ Telegram ใช้ service/transaction เดียวกัน
- Supabase Dashboard ใช้ดูตารางและงานฉุกเฉินได้ ทางปรับยอดประจำคือเว็บที่บันทึก ledger ด้วย หากปรับ SQL ต้องผ่านฟังก์ชันปรับยอดที่มีสิทธิ์ actor/reason/audit ไม่แก้ balance ตรงจน ledger ไม่ตรง

## 6. Binance UID อัตโนมัติด้วยยอดทศนิยม 3–4 หลัก

### เป้าหมายและเงื่อนไขพร้อมใช้

ผู้ใช้ไม่ต้องส่งสลิป กรอก transaction ID หรือกดตรวจเอง ระบบอ่านเงินเข้าจริงจากบัญชีรับและจับคู่ยอดเฉพาะ คำขอผูกกับ user ID ตั้งแต่สร้าง ไม่อาศัยชื่อผู้โอนเป็นตัวจับคู่

API ที่ตรวจคือ GET /sapi/v1/pay/transactions แบบ signed มี transactionId, transactionTime, amount และ currency ยอดบวกหมายถึงเงินเข้า เอกสารรองรับ amount ถึง 8 ทศนิยม แต่ยังต้องตรวจว่าหน้าส่ง Binance Pay/UID ที่ใช้จริงยอมให้โอนและรับตรง 3–4 ทศนิยม และบัญชีรับอ่านรายการชนิดนั้นได้ การสร้าง API key ไม่ยืนยันเงื่อนไขนี้โดยลำพัง

ตรวจว่าใช้ Binance UID หรือ Pay ID และทิศทางรายการจากบัญชีจริง ไม่สลับกับ Merchant API และไม่ใช้ UID ในภาพคนอื่น ถ้า API/precision ใช้ไม่ได้ต้องแจ้งเพื่อทบทวนวิธีรับเงิน ไม่เปลี่ยนเป็น admin approval เป็นเส้นทางหลักโดยพลการ เพราะเจ้าของต้องการอัตโนมัติ

### สร้างยอดเฉพาะ

1. ผู้ใช้เลือกยอดฐานเป็นจำนวนบวก เสนอรับฐานได้สูงสุด 2 ทศนิยม จากนั้นเพิ่มเศษเล็ก ๆ เช่น ฐาน 1.00 → โอน 1.0037 USDT; ฐาน 5.00 → โอน 5.008 USDT
2. ใช้ 4 หลักเป็นค่าเริ่มต้น รองรับตั้งค่า 3 หลัก; กำหนดช่วงเศษที่เพิ่มให้ชัด เช่น 0.0001–0.0099 สำหรับโหมด 4 หลัก หรือ 0.001–0.009 สำหรับโหมด 3 หลัก
3. สุ่มและจองยอดสุทธิใน DB transaction ป้องกันชนภายใต้บัญชีรับ+สกุลเงิน ตรวจทั้งต่างยอดฐาน/precision ไม่สุ่มแล้วเชื่อว่าไม่ซ้ำ
4. แสดงยอดโอนตรงตามทศนิยม UID เครดิตที่จะได้รับ และเวลาหมดอายุชัดเจน ไม่ต้องใส่ note/remark เพื่อจับคู่
5. เสนออายุ 8 นาทีตามภาพ หนึ่ง pending request ต่อ user กดซ้ำแสดงเดิม จำกัดความถี่การสร้าง/ยกเลิกป้องกันจองช่องจนหมด
6. หายอดว่างไม่ได้ให้แจ้งรอหรือเลือกยอดฐานอื่น ไม่ออกยอดชน และไม่ขยายช่วงเศษโดยไม่แจ้งยอด/เครดิตจริง

จำนวนช่องมีจำกัด: ช่วงเศษตัวอย่างให้ 99 ยอดในโหมด 4 หลัก หรือ 9 ยอดในโหมด 3 หลักต่อฐานที่ไม่ทับกัน ต้องตรวจความจุและเลือกช่วงเศษที่ยอมรับได้ก่อนเปิดจริง การรองรับ 3 หลักไม่ใช่มีพื้นที่มากเท่า 4 หลัก

### ตรวจและลงเครดิต

1. Worker poll ประวัติรวมตาม rate limits จริง ใช้ backoff ไม่ดึงหนึ่งครั้งต่อผู้ขอเติมแต่ละคน
2. เก็บ payment event จากบัญชีรับจริง ดึงซ้อนช่วงเวลาและไล่ขอบเขตผลลัพธ์ให้ครบ (endpoint จำกัด 100 รายการต่อคำขอ) ไม่อ่านเฉพาะหน้าแรก
3. ตรวจประเภทรับโอนที่รองรับ ทิศทางรับ สถานะสำเร็จตาม semantics ที่พิสูจน์จาก API ยอดบวก USDT ผู้รับ ยอดตรงเป๊ะ และเวลาธุรกรรมอยู่ในช่วงจอง
4. เก็บ checkpoint/watermark ถาวร เลื่อนหลังอ่านครบและบันทึกสำเร็จเท่านั้น ไม่ข้ามช่วงที่ API error มี reconciliation ย้อนหลังรองรับข้อมูลมาช้าและ downtime
5. ล็อกคำขอ/ยอดผู้ใช้ ตรวจ transactionId ยังไม่ใช้ → ผูก event กับคำขอเดียว → เพิ่ม ledger/เครดิต → paid → outbox Telegram/Discord ภายใน transaction เดียว
6. Worker ซ้ำ restart หรือแอดมินแก้พร้อมกันต้องเติมได้ครั้งเดียวด้วย unique transaction และ ledger reference

### หมดอายุ ยกเลิก และโอนช้า

- ใช้เวลาธุรกรรมจาก provider ไม่ใช่แค่เวลาที่ worker พบ โอนในเวลาคำขอแต่ API พบช้ายังจับคู่เดิมได้ถ้าไม่กำกวม
- โอนหลังหมดอายุ/ยกเลิก ยอดผิด สกุลผิด หรือแยกเจ้าของไม่ได้ → needs_review; ให้แอดมินแก้ exception พร้อม audit ไม่เครดิตเข้าคำขอใหม่โดยเดา
- ยกเลิกหยุดหน้ารอ แต่คงประวัติและการกันยอด ไม่ปล่อยยอดสุทธิเก่ากลับใช้ทันที
- ค่าเริ่มต้นเพื่อป้องกันเครดิตผิดคน: ไม่ reuse ยอดสุทธิที่เคยออกในบัญชี/สกุลเงินเดียวกัน หากยังไม่มีหลักฐานผู้จ่าย/อ้างอิงที่ API ตรวจสอบได้เพิ่มเติม ช่องเต็มให้เลือกฐานอื่นหรือทบทวนวิธีจับคู่
- Cooldown เช่น 24 ชั่วโมงอย่างเดียวไม่แก้ปัญหาคนโอนยอดเก่าในภายหลัง จึงไม่ถือว่าเวลารอทำให้ reuse ปลอดภัย หากจะ reuse ต้องออกแบบยืนยันผู้จ่ายเพิ่มและอนุมัตินโยบายก่อน
- ยอดสุ่มเป็นตัวช่วยจับคู่ ไม่ใช่หลักฐานตัวตนแน่นอน ใครที่รู้ยอดอาจโอนแทนได้ จึงเก็บยอด pending เป็นข้อมูลส่วนตัวและไม่เปิดใน Discord ก่อน paid
- ไม่ใช้ transaction ID จากผู้ใช้เพื่อ claim เงินคนอื่น ตรวจ unmatched events บนหน้าแอดมิน ไม่ละทิ้งรายการ
- API/DB ล่มหยุดออกยอดที่จองไม่ได้ และตรวจย้อนหลังหลังฟื้น ไม่เติมจากสลิป/ข้อความผู้ใช้ หาก outage เกินประวัติที่ API เรียกได้ต้องมี reconciliation โดยแอดมิน

## 7. วิธีสร้าง API key Binance สำหรับงานนี้

คำแนะนำตามคู่มือทางการที่ตรวจวันที่ 2026-10-20 หน้าจออาจต่างตามบัญชี/ภูมิภาค รอบนี้ยังไม่มีการสร้าง key หรือเข้าบัญชีจริง

1. เข้า Binance ด้วยตัวเอง → โปรไฟล์ → Account → API Management → Create API
2. ผ่านเงื่อนไขยืนยันบัญชี/2FA ตามที่เว็บกำหนด ตั้งชื่อแยก เช่น Telegram-Topup-Reader
3. เลือกชนิด key ที่ implementation รองรับ; system-generated ใช้ API key/secret แบบ HMAC ส่วน self-generated เป็นอีกชนิด ต้องเลือกให้ตรง connector ภายหลัง
4. ให้เฉพาะสิทธิ์อ่านที่จำเป็น ไม่เปิดซื้อขาย ถอน หรือ transfer ตั้ง IP restriction ให้ public outbound IPv4 ของ VPS ที่ตรวจจริง
5. เก็บ key/secret ใน environment บน VPS หรือ secret manager ไม่ส่งในแชท ไม่ใส่ Git/plan/browser bundle/Discord/Supabase ตารางทั่วไป
6. หลังอนุมัติพัฒนา ทดสอบ signed request อ่าน Pay history และเวลาระบบ หาก permission denied ให้ตรวจเอกสาร/บัญชี ไม่เปิดสิทธิ์การเงินเพิ่มเพื่อเดาแก้
7. ก่อนเปิดจริง ให้เจ้าของอนุญาตและทำรายการทดสอบเล็กด้วยตัวเอง พิสูจน์ UID/precision/ยอดรับ/transaction ID/เครดิตครั้งเดียว แล้วจัดทำคู่มือ rotate/revoke key

อ้างอิง: [Binance API key guide](https://www.binance.com/en/support/faq/detail/360002502072), [Binance Pay REST API](https://developers.binance.com/docs/pay/rest-api)

## 8. Database ภายนอก: Supabase Free

ใช้ PostgreSQL ของ Supabase นอก VPS มี Dashboard/Table Editor/SQL Editor และเชื่อมเว็บแอดมินของเรา ไม่ใช้ SQLite หรือ DB production บนเครื่อง VPS

- หน้าราคาที่ตรวจระบุ Free $0, database 500 MB, egress 5 GB และพักหลัง inactivity 1 สัปดาห์ Automatic backup ไม่รวม Free ต้องเฝ้า quota/สถานะและสำรองเอง ไม่รับรอง SLA จากบริการฟรี
- ตัวเลขเป็นข้อมูลวันที่ตรวจ ไม่รับประกันตลอดไป ไม่เพิ่มบริการเสียเงินอัตโนมัติ
- Backend เชื่อม TLS และใช้ pool ตาม Supabase/driver ที่เลือก ไม่ใส่ DB password/service-role/secret key ใน frontend
- การเงิน/การจัดสรรใช้ PostgreSQL transaction ผ่าน backend ไม่เรียก REST หลายครั้งแล้วถือว่า atomic
- เปิด RLS กับตารางที่ expose ผ่าน API และ policies ชัดเจน ไม่เปิด anonymous อ่านคลัง/ledger; service role bypass RLS จึงต้องเก็บฝั่ง server และตรวจสิทธิ์ทุกทางที่ใช้
- DB พัก/ล่มให้แจ้งชั่วคราว หยุดธุรกรรมที่บันทึกไม่ได้ ไม่สร้างยอดสำรองใน memory แล้วเดาว่าจะ sync ภายหลัง
- สำรอง logical export ที่ปลอดภัยพร้อม schema/ส่วนที่จำเป็นตาม provider และซ้อม restore ก่อน production

### ตารางหลัก

| ตาราง | หน้าที่ |
|---|---|
| users | Telegram ID unique, balance_units ≥ 0, สร้างอัตโนมัติ |
| admin_identities | ผูก Telegram admin ID/เว็บ Auth subject กับ role ที่ owner มอบ |
| email_batches/email_inventory | import metadata, email, dedup key unique, available/allocated/deleted ไม่มี password |
| orders/order_items | ราคา snapshot, เจ้าของ, nonce unique, email_id unique |
| wallet_ledger | delta, ก่อน/หลัง, actor, reason, reference unique |
| topup_requests | user, base/expected/credited amount, precision, created/expires/cancelled/paid |
| amount_leases | receiver/currency/normalized amount ประวัติการจอง; DB บังคับไม่ออกยอดเก่าซ้ำตามนโยบาย |
| payment_events | provider/account/transactionId unique, เวลา ยอด สกุล ประเภท และ request ที่ผูก |
| payment_checkpoints | ช่วงที่ดึงครบแล้ว/จุดตรวจต่อหลัง restart |
| delivery_outbox | Telegram text/file parts, retries และ order เดิม |
| notification_outbox | Discord event/channel unique และผลส่ง/retries |
| audit_events/settings | ปรับยอด ลบเมล เปลี่ยนราคา สิทธิ์ และ config ที่ไม่ใช่ secrets |

เวลาเก็บ UTC แสดงเวลาไทย แยก handlers/service/repository ไม่แก้ shared state แทน transaction และ ledger เป็นประวัติแบบเพิ่มรายการ

## 9. เว็บแอดมิน

เป็นส่วนหนึ่งของ scope ไม่ใช่แค่ลิงก์ Dashboard ของ provider ใช้ผ่านมือถือ/คอมได้

| หน้า | การใช้งาน |
|---|---|
| Login | Supabase Auth + ตรวจ admin_identities ฝั่ง backend ปิด public sign-up ของเว็บแอดมิน |
| ภาพรวม | ยอดเติม/ซื้อ จำนวนคลัง และงานค้าง |
| ผู้ใช้/เครดิต | ค้น Telegram ID/ชื่อ ดู ledger ปรับเพิ่ม/ลด/กำหนดยอดพร้อมเหตุผลและยืนยัน |
| คลังเมล | ค้น available/sold/deleted นำเข้าข้อความ/.txt preview เพิ่มลบรายอัน/เป็นชุด |
| เติมเงิน | ยอดฐาน/ยอดจริง เวลาหมดอายุ events และ needs_review พร้อม audit |
| คำสั่งซื้อ | ยอดหักและสถานะไฟล์/ข้อความแต่ละส่วน ส่งซ้ำหรือคืนตามนโยบาย |
| ประวัติแอดมิน | ใครปรับยอดหรือลบอะไร เมื่อไร พร้อมเหตุผล |

เสนอ Python + FastAPI + HTML templates ที่ใช้มือถือได้ ลดจำนวนบริการและใช้ logic ร่วมบอท เหมาะกับทรัพยากร VPS ที่ระบุ โดยยังต้องวัดสภาพเครื่องจริงก่อนกำหนด workers

HTTPS, ตรวจ session/token และ role ทุก endpoint, ป้องกัน CSRF สำหรับ cookie-based actions, escape XSS, parameterized SQL, rate limits login/actions และการเพิกถอนสิทธิ์ต้องมีผลจริง ไม่ expose SQL editor สาธารณะ บัญชีเว็บกับ Telegram ผูกโดย owner เท่านั้น

## 10. Discord webhook แยก 2 ห้อง

- ตั้ง DISCORD_TOPUP_WEBHOOK_URL และ DISCORD_ORDER_WEBHOOK_URL คนละค่า เก็บ server secrets เจ้าของสร้างห้อง/URL ภายหลัง รอบนี้ไม่ส่งข้อความจริง
- ห้องเติมเงิน: แจ้งหลังเครดิต commit สำเร็จ มี user ID/ชื่อที่ escape, เลขเติม, USDT รับจริง, credit เพิ่ม, ยอดเหลือ, เวลา ไม่แจ้ง success ตอนสร้าง pending
- ห้องซื้อเมล: แจ้งหลัง order commit มี user ID/order, จำนวน, ราคาต่อเมล, ยอดหัก/เหลือ และสถานะส่ง หากยังไม่ครบระบุ pending และอัปเดตหลังครบเมื่อมี message ID
- ไม่แนบเมลที่ซื้อ password token key หรือ webhook URL ลง Discord จำกัดห้องเฉพาะผู้ดูแล
- บันทึก outbox พร้อม transaction ธุรกรรม ใช้ unique event/channel กัน enqueue ซ้ำ Discord ล่มไม่ rollback เครดิต/การซื้อ
- ใช้ wait=true รับการยืนยัน/message ID เคารพ 429/retry_after และ retry/backoff แสดงค้างบนเว็บ
- Timeout หลัง Discord รับอาจมีข้อความเดิมซ้ำ ใช้เลขรายการตรวจได้ ไม่สัญญา exactly-once
- ปิด allowed_mentions และ escape input ไม่ให้ชื่อผู้ใช้ ping @everyone/@role

## 11. โครงสร้างและลำดับพัฒนาหลังอนุมัติ

พัฒนาด้วย Python + aiogram 3, FastAPI/templates, SQLAlchemy + psycopg และ pytest/pytest-cov ใช้ Telegram long polling และ workers สำหรับ payments/delivery/notifications มี requirements.lock.txt; schema รุ่นแรกใช้ init-db เป็น baseline เท่านั้น ไม่ใช่ migration อัปเกรดอัตโนมัติ รุ่นถัดไปที่เปลี่ยน schema ต้องเพิ่ม migration แยก

```text
src/team_mail_bot/
  cli.py, config.py
  core.py       # ธุรกรรม เครดิต คลัง orders/topups และ audit
  db.py, models.py
  payments.py   # Binance reader และ reconciliation
  workers.py    # งานส่ง Telegram/Discord
  telegram_bot.py
  admin_web.py, templates/
  logging_utils.py
tests/          # unit/integration/E2E/real PostgreSQL tests
deploy/         # services/env ตัวอย่างไม่มี secrets
```

| ระยะ | งานหลัก/ไฟล์ | เกณฑ์ผ่าน/ขึ้นกับ |
|---|---|---|
| 0 | ตรวจ Binance API, UID/precision, Supabase connectivity | หลังอนุมัติ หาก auto ใช้ไม่ได้ทบทวนก่อนสร้างเต็ม |
| 1 | config/access/db/.gitignore | ผู้ใช้ใหม่เข้าได้ แอดมินแยก; แก้ tests/ ที่ ignore เดิมให้เก็บใน Git |
| 2 | wallet/inventory/migrations | ledger ตรง import ไม่มี password ลบไม่ทำประวัติขาด |
| 3 | admin_web/Auth | เฉพาะแอดมินแก้เครดิต/เพิ่มลบเมล ใช้ logic ร่วม Telegram |
| 4 | orders/telegram/outbox | ด่วน .30 ครั้งเดียว bulk ไฟล์หนึ่งชุดและข้อความครบ กู้ส่งต่อได้ |
| 5 | payments/leases/checkpoints | ไม่ออกยอดชน ตรวจเงินอัตโนมัติ ไม่เติมซ้ำ/ผิดคน |
| 6 | notifications/Discord | สองห้องถูกประเภท ส่งหลัง commit ล่มไม่กระทบยอด |
| 7 | tests/deploy/คู่มือใน docs ที่ตกลง | coverage ≥80%, review critical paths และซ้อม restore |

ก่อน feature ใช้ TDD: RED → GREEN → REFACTOR ใช้ planner/tdd-guide ตามงาน และ code-reviewer/security-reviewer ตรวจสิทธิ์/การเงิน แก้ critical/high ก่อนส่งมอบ อัปเดต PROJECT_PLAN.md/CHANGELOG.md ตามงานจริง

## 12. แผนทดสอบและเกณฑ์รับงาน

- Unit: parser หลายระดับโดเมน อีเมลล้วน/เลข/password มี @, dedup, ราคา .30, Decimal, ทศนิยม 3/4, 1.230=1.2300, Telegram/web permission
- Integration บน PostgreSQL: สองคนแย่งเมลสุดท้าย ซื้อกับลบ/ปรับเครดิตพร้อมกัน stale web form callback ซ้ำ rollback และ outbox restart
- Topup: ยอดสุ่มชน/ช่องเต็ม ฐานต่างกันแต่ยอดสุทธิตรง คำขอซ้ำ expiry/cancel ไม่ reuse โอนช้า ซ้ำยอดเดิมสองครั้ง ประวัติสลับลำดับ เกิน 100 รายการ crash ก่อน checkpoint และ API outage
- กรณีตัวเลข: รับ 1.0037 USDT เพิ่ม 1.0037 credit ครั้งเดียว ซื้อ 1 เมลเหลือ .7037; 5 เมลหัก 1.50
- E2E จำลอง: ผู้ใช้ใหม่เข้าได้ทันที → เติมยอดเฉพาะ → API พบ → เครดิตเข้า → ซื้อ → ได้ไฟล์/ข้อความครบ → Discord สองห้องถูกประเภท
- Security: anonymous/member ปลอม admin callback/API ไม่ได้ IDOR/RLS/SQL/XSS/CSRF ตาม surface ไม่มี password/secrets ใน DB/log/browser/Discord
- Delivery: ยาวแบ่งครบ ไม่มีเมลถูกตัด ไฟล์หนึ่งชุด partial failure ส่งต่อ order เดิม 429/timeout/block และ Discord ล่มไม่หักซ้ำ
- Automated coverage ≥80% ของโปรแกรม พร้อม assertions สำคัญด้านยอด/สิทธิ์/จัดสรร ไม่ใช้ coverage แทน correctness
- ก่อน production ทดสอบ test bot/Discord ห้องทดสอบและเงินจริงเล็กที่เจ้าของอนุญาตภายหลัง รอบนี้ไม่มีการทดสอบระบบเพราะแก้เฉพาะเอกสาร

## 13. VPS และการดูแล

- ตรวจ OS จริงก่อนติดตั้ง หากเป็น Ubuntu 20.04 standard security maintenance สิ้นสุดแล้ว ต้องตรวจ Ubuntu Pro/ESM หรือวางแผนอัปเกรด LTS ที่รองรับก่อนเปิดบริการ ไม่อัปเกรดเองในรอบนี้
- 2 core/4 GB เป็นข้อมูลประมาณ ตรวจพื้นที่/บริการเดิม กำหนด workers/connections เหมาะสม ไม่รัน DB production บน VPS
- รัน bot/worker/web แยก GNU Screen sessions บน VPS ด้วยบัญชี non-root; ใช้ systemd เปิดหลัง VPS boot และ restart โปรเซสเมื่อจบเอง พร้อม reverse proxy HTTPS สำหรับเว็บ
- ตกลงโดเมน/HTTPS ก่อนเปิดเว็บ ไม่ใส่ API/DB/Discord secrets ใน public assets
- สำรอง Supabase แบบ logical export เสนอรายวัน 7 ชุด/รายสัปดาห์ 4 ชุด เข้ารหัส มีสำเนาแยกจาก VPS และตรวจโควตา/retention
- ซ้อม restore กระทบยอด ledger/orders/payment checkpoints/outbox ก่อนเปิดรับงาน
- ดูแล quota/DB paused, poll ล่าช้า, unmatched payment และ notification ค้างผ่านหน้าดูแลที่ผู้ใช้ทั่วไปเข้าไม่ได้

## 14. ค่าที่เสนอและข้อมูลที่ต้องใช้ภายหลัง

ไม่ถามราคา อัตราเครดิต สิทธิ์สมาชิก ประเภทเมล หรือส่ง bulk ซ้ำ เพราะยืนยันแล้ว เหลือ:

1. ค่าเสนอ: อายุ 8 นาที ค่าเริ่มต้นทศนิยม 4/รองรับ 3 ช่วงเศษเล็กตามหัวข้อ 6 ไม่ reuse ยอดเก่าหากขาดตัวระบุผู้จ่าย และเครดิตตามรับจริงรวมเศษ
2. สร้าง/เลือก region Supabase Free หลังอนุมัติ พร้อมรับทราบโควตา/inactivity; ไม่เก็บ DB ใน VPS
3. ตั้ง owner/admin Telegram IDs และเว็บ identities เลือกโดเมน/HTTPS
4. ยืนยัน OS/IP จริง receiver UID/Pay ID สิทธิ์ API และ precision จริงภายหลัง
5. สร้าง Discord สองห้องและ webhook สอง URL เก็บเป็น secrets

needs_review ใช้เฉพาะ exception เส้นทางปกติเป็นอัตโนมัติ ไม่ลดเหลือแอดมินอนุมัติเป็นค่าเริ่มต้น มี implementation แล้วตามอนุมัติ ใช้โควตาสร้างคำขอที่ยังไม่เครดิต 3 ครั้งต่อ 24 ชั่วโมงและเว้น 60 วินาที เพื่อลดการจองยอดทิ้ง; รายการ paid ไม่กินโควตานี้ ข้อจำกัด namespace ถาวร/หลายบัญชียังต้องรับทราบตามคู่มือ

## 15. อ้างอิงและเอกสารส่งมอบ

ตรวจข้อมูลวันที่ 2026-10-20 ราคา โควตา หน้าจอและข้อกำหนด API ต้องตรวจซ้ำเมื่อพัฒนา

- [Supabase Pricing](https://supabase.com/pricing) — Free/โควตา/inactivity/backup
- [Supabase Auth](https://supabase.com/docs/guides/auth) และ [RLS](https://supabase.com/docs/guides/database/postgres/row-level-security) — สิทธิ์เว็บและข้อมูล
- [Binance Pay REST API](https://developers.binance.com/docs/pay/rest-api) — history/amount/transactionId/limits
- [Binance API key guide](https://www.binance.com/en/support/faq/detail/360002502072) — สร้าง key/ชนิด key
- [Telegram Bot API](https://core.telegram.org/bots/api) — messages/files/callback
- [Discord Webhooks](https://discord.com/developers/docs/resources/webhook) — wait/allowed_mentions
- [Ubuntu release cycle](https://ubuntu.com/about/release-cycle) — อายุการสนับสนุน 20.04

plan.md เป็นแผนหลัก PROJECT_PLAN.md บันทึกสถานะ/เฟส CHANGELOG.md บันทึกการเปลี่ยนแปลง โค้ดมีแล้วและผ่าน 141 tests (coverage 92.24%) รวม PostgreSQL จริง 6 tests; ยังไม่เชื่อมบัญชี production/โอนเงินจริง/deploy ดูผลและข้อจำกัดใน docs/VALIDATION.md
