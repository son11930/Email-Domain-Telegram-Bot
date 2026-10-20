"""Transactional application boundary shared by Telegram, web and workers."""
import re
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .models import (
    AmountLease,
    Audit,
    Checkpoint,
    Email,
    Ledger,
    Order,
    OrderItem,
    Outbox,
    Payment,
    Setting,
    Topup,
    User,
)

UNITS = 100_000_000
MAX_UNITS = 9_000_000_000_000_000

class DomainError(Exception):
    """A safe, user-visible validation or business rule failure."""

def utcnow():
    return datetime.now(UTC)

def aware(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

def dto(row):
    return {column.name: (aware(value).isoformat() if isinstance(value := getattr(row, column.name), datetime) else value)
            for column in row.__table__.columns}

def insert_once(session, model, values, key):
    dialect_insert = pg_insert if session.bind.dialect.name == 'postgresql' else sqlite_insert
    statement = dialect_insert(model).values(**values).on_conflict_do_nothing(index_elements=[key]).returning(getattr(model, key))
    return session.execute(statement).first() is not None

def positive_id(value):
    if type(value) is not int or not 0 < value < 2**63:
        raise DomainError('Invalid user ID')

def money(value, positive=False):
    if type(value) is not int or abs(value) > MAX_UNITS or (positive and value <= 0):
        raise DomainError('Invalid amount')

def request_key(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 120:
        raise DomainError('Invalid request key')

def reason_text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise DomainError('A reason is required (maximum 500 characters)')

def actor_text(value):
    if type(value) is int and 0 < value < 2**63:
        return str(value)
    if isinstance(value, str) and value.startswith('web:') and 4 < len(value) <= 160:
        return value
    raise DomainError('Invalid administrator identity')

class AppService:
    def __init__(self, session_factory, *, price_units=30_000_000, precision=4,
                 topup_ttl_seconds=480, max_order_quantity=1000, topup_daily_limit=3,
                 topup_cooldown_seconds=60, outbox_lease_seconds=300):
        money(price_units, True)
        if precision not in (3, 4) or not 30 <= topup_ttl_seconds <= 3600:
            raise ValueError('Invalid topup configuration')
        if type(max_order_quantity) is not int or not 1 <= max_order_quantity <= 10000:
            raise ValueError('Invalid order limit')
        if type(topup_daily_limit) is not int or not 1 <= topup_daily_limit <= 100:
            raise ValueError('Invalid topup issuance limit')
        if type(topup_cooldown_seconds) is not int or not 0 <= topup_cooldown_seconds <= 3600:
            raise ValueError('Invalid topup cooldown')
        if type(outbox_lease_seconds) is not int or not 30 <= outbox_lease_seconds <= 3600:
            raise ValueError('Invalid outbox lease duration')
        self.factory = session_factory
        self.price_units = price_units
        self.precision = precision
        self.topup_ttl_seconds = topup_ttl_seconds
        self.max_order_quantity = max_order_quantity
        self.topup_daily_limit = topup_daily_limit
        self.topup_cooldown_seconds = topup_cooldown_seconds
        self.outbox_lease_seconds = outbox_lease_seconds

    def _user(self, session, user_id, lock=False):
        positive_id(user_id)
        statement = select(User).where(User.id == user_id)
        row = session.scalar(statement.with_for_update() if lock else statement)
        if row is None:
            raise DomainError('User not found; send /start first')
        return row

    def ensure_user(self, user_id, name=''):
        positive_id(user_id)
        if not isinstance(name, str):
            raise DomainError('Invalid display name')
        with self.factory.begin() as session:
            insert_once(session, User, {'id': user_id, 'name': name[:256], 'balance_units': 0}, 'id')
            user = self._user(session, user_id, True)
            user.name = name[:256]
            return dto(user)

    def get_user(self, user_id):
        with self.factory() as session:
            return dto(self._user(session, user_id))

    def list_users(self, query=''):
        with self.factory() as session:
            statement = select(User).order_by(User.id)
            if query:
                search = str(query)
                statement = statement.where(or_(cast(User.id, String).icontains(search, autoescape=True),
                                                User.name.icontains(search, autoescape=True)))
            return [dto(row) for row in session.scalars(statement)]

    def summary(self):
        with self.factory() as session:
            count = lambda model, *clauses: session.scalar(select(func.count()).select_from(model).where(*clauses))
            return {'users': count(User), 'available_emails': count(Email, Email.status == 'available'),
                    'orders': count(Order), 'pending_topups': count(Topup, Topup.status == 'pending'),
                    'needs_review': count(Payment, Payment.status == 'needs_review'),
                    'pending_outbox': count(Outbox, Outbox.status != 'done'),
                    'total_sales_units': session.scalar(select(func.coalesce(func.sum(Order.total_units), 0))),
                    'total_topup_units': session.scalar(select(func.coalesce(func.sum(Payment.amount_units), 0)).where(Payment.status == 'paid')),
                    'price_units': self._price(session)}

    def _price(self, session, lock=False, *, shared_lock=False):
        insert_once(session, Setting, {'name': 'price_units', 'value': self.price_units}, 'name')
        query = select(Setting).where(Setting.name == 'price_units')
        row = session.scalar(query.with_for_update(read=shared_lock) if lock or shared_lock else query)
        return row.value

    def get_price(self):
        with self.factory.begin() as session:
            return self._price(session)

    def get_stock(self):
        with self.factory() as session:
            return session.scalar(select(func.count()).select_from(Email).where(Email.status == 'available'))

    def set_price(self, actor_id, price_units, reason):
        actor_id = actor_text(actor_id)
        money(price_units, True)
        reason_text(reason)
        with self.factory.begin() as session:
            self._price(session, True)
            row = session.get(Setting, 'price_units')
            before = row.value
            row.value = price_units
            session.add(Audit(actor_id=actor_id, action='set_price', details={
                'before_units': before, 'price_units': price_units, 'reason': reason}))
            return {'price_units': price_units}

    def preview_import(self, text):
        if not isinstance(text, str) or len(text.encode('utf-8')) > 2_000_000:
            raise DomainError('Import too large (maximum 2 MB)')
        valid, seen, invalid, duplicates = [], set(), 0, 0
        for line in text.splitlines():
            line = line.strip()
            if not line or re.fullmatch(r'\d+[.)]?', line):
                continue
            candidate = re.sub(r'^\d+[.)]\s*', '', line).split('|', 1)[0].strip()
            if len(candidate) > 254 or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}", candidate):
                invalid += 1
                continue
            local, domain = candidate.rsplit('@', 1)
            if len(local) > 64 or local.startswith('.') or local.endswith('.') or '..' in candidate or any(len(x) > 63 or x.startswith('-') or x.endswith('-') for x in domain.split('.')):
                invalid += 1
                continue
            email = local + '@' + domain.lower()
            if email in seen:
                duplicates += 1
            else:
                valid.append(email)
                seen.add(email)
        if len(valid) > 10000:
            raise DomainError('Maximum 10000 emails per import')
        with self.factory() as session:
            existing = set(session.scalars(select(Email.email).where(Email.email.in_(valid)))) if valid else set()
        return {'valid': [email for email in valid if email not in existing],
                'invalid': invalid, 'duplicates': duplicates + len(existing)}

    def import_emails(self, actor_id, text):
        actor_id = actor_text(actor_id)
        preview = self.preview_import(text)
        added = 0
        with self.factory.begin() as session:
            dialect_insert = pg_insert if session.bind.dialect.name == 'postgresql' else sqlite_insert
            for start in range(0, len(preview['valid']), 400):
                values = [{'email': email, 'status': 'available'} for email in preview['valid'][start:start + 400]]
                statement = dialect_insert(Email).values(values).on_conflict_do_nothing(
                    index_elements=[Email.email]).returning(Email.id)
                added += len(session.scalars(statement).all())
            result = {'added': added, 'duplicate': preview['duplicates'] + len(preview['valid']) - added, 'invalid': preview['invalid']}
            session.add(Audit(actor_id=actor_id, action='import_emails', details=result))
        return result

    def list_emails(self, status='available', query=''):
        if status == 'sold':
            status = 'allocated'
        if status not in ('available', 'allocated', 'deleted', 'all'):
            raise DomainError('Invalid inventory status')
        with self.factory() as session:
            statement = select(Email).order_by(Email.id.desc())
            if status != 'all':
                statement = statement.where(Email.status == status)
            if query:
                statement = statement.where(Email.email.icontains(str(query), autoescape=True))
            return [dto(row) for row in session.scalars(statement)]

    def delete_email(self, actor_id, email_id, reason):
        actor_id = actor_text(actor_id)
        reason_text(reason)
        with self.factory.begin() as session:
            row = session.scalar(select(Email).where(Email.id == email_id).with_for_update())
            if row is None or row.status != 'available':
                raise DomainError('Only available emails can be deleted')
            row.status = 'deleted'
            session.add(Audit(actor_id=actor_id, action='delete_email', details={'email_id': email_id, 'reason': reason}))
            return dto(row)

    def delete_emails(self, actor_id, email_ids, reason):
        actor_id = actor_text(actor_id)
        reason_text(reason)
        if (not isinstance(email_ids, list) or not 1 <= len(email_ids) <= 500
                or any(type(value) is not int or not 0 < value < 2**63 for value in email_ids)):
            raise DomainError('Choose between 1 and 500 valid email IDs')
        identifiers = sorted(set(email_ids))
        with self.factory.begin() as session:
            rows = list(session.scalars(select(Email).where(Email.id.in_(identifiers))
                                        .order_by(Email.id).with_for_update()))
            if len(rows) != len(identifiers) or any(row.status != 'available' for row in rows):
                raise DomainError('All selected emails must exist and be available')
            for row in rows:
                row.status = 'deleted'
            session.add(Audit(actor_id=actor_id, action='delete_emails', details={
                'email_ids': identifiers, 'reason': reason, 'deleted': len(rows)}))
            return {'deleted': len(rows)}

    def _ledger(self, session, user, delta, reference, reason, actor_id=None):
        new_balance = user.balance_units + delta
        if not 0 <= new_balance <= MAX_UNITS:
            raise DomainError('Insufficient credit or balance exceeds limit')
        session.add(Ledger(user_id=user.id, delta_units=delta, before_units=user.balance_units,
                           after_units=new_balance, actor_id=actor_id, reason=reason, reference=reference))
        user.balance_units = new_balance

    def adjust_credit(self, actor_id, user_id, delta_units=None, target_units=None, reason='', request_key='', expected_balance_units=None):
        actor_id = actor_text(actor_id)
        reason_text(reason)
        globals()['request_key'](request_key)
        if (delta_units is None) == (target_units is None):
            raise DomainError('Specify either a delta or a target')
        money(delta_units if delta_units is not None else target_units)
        reference = 'admin:' + request_key
        with self.factory.begin() as session:
            user = self._user(session, user_id, True)
            previous = session.scalar(select(Ledger).where(Ledger.reference == reference))
            if previous:
                if previous.user_id != user_id or previous.actor_id != actor_id:
                    raise DomainError('Request key already used')
                return {'id': previous.id, 'user_id': user_id, 'balance_units': previous.after_units, 'delta_units': previous.delta_units}
            if expected_balance_units is not None and expected_balance_units != user.balance_units:
                raise DomainError('Balance changed; review and confirm again')
            delta = delta_units if delta_units is not None else target_units - user.balance_units
            self._ledger(session, user, delta, reference, reason, actor_id)
            session.add(Audit(actor_id=actor_id, action='adjust_credit', details={'user_id': user_id, 'delta_units': delta, 'reason': reason}))
            session.flush()
            row = session.scalar(select(Ledger).where(Ledger.reference == reference))
            return {'id': row.id, 'user_id': user_id, 'balance_units': user.balance_units, 'delta_units': delta}

    def list_audit(self):
        with self.factory() as session:
            return [dto(row) for row in session.scalars(select(Audit).order_by(Audit.id.desc()))]

    def _order(self, session, order):
        emails = session.scalars(select(Email.email).join(OrderItem, OrderItem.email_id == Email.id)
                                 .where(OrderItem.order_id == order.id).order_by(OrderItem.id)).all()
        return {**dto(order), 'emails': list(emails)}

    def purchase(self, user_id, quantity, request_key, expected_price_units=None):
        globals()['request_key'](request_key)
        if type(quantity) is not int or not 1 <= quantity <= self.max_order_quantity:
            raise DomainError('Invalid order quantity')
        key = f'{user_id}:{request_key}'
        with self.factory.begin() as session:
            user = self._user(session, user_id, True)
            previous = session.scalar(select(Order).where(Order.request_key == key))
            if previous:
                return self._order(session, previous)
            price = self._price(session, shared_lock=True)
            if expected_price_units is not None and expected_price_units != price:
                raise DomainError('Price changed; please confirm the new price')
            total = quantity * price
            if user.balance_units < total:
                raise DomainError('Insufficient credit')
            inventory = list(session.scalars(select(Email).where(Email.status == 'available').order_by(Email.id)
                                             .limit(quantity).with_for_update(skip_locked=True)))
            if len(inventory) != quantity:
                raise DomainError('Not enough emails available; please try again later')
            order_id = str(uuid4())
            self._ledger(session, user, -total, 'order:' + order_id, 'Email purchase')
            order = Order(id=order_id, user_id=user_id, quantity=quantity, request_key=key,
                          price_units=price, total_units=total, balance_units=user.balance_units, status='pending')
            session.add(order)
            session.flush()
            for email in inventory:
                email.status = 'allocated'
                session.add(OrderItem(order_id=order_id, email_id=email.id))
            self._enqueue(session, 'telegram_order', {'order_id': order_id, 'user_id': user_id}, 'telegram_order:' + order_id)
            self._enqueue(session, 'discord_order', {'order_id': order_id, 'user_id': user_id, 'quantity': quantity,
                          'total_units': total, 'balance_units': user.balance_units, 'status': 'pending'}, 'discord_order:' + order_id)
            session.flush()
            return self._order(session, order)

    def list_orders(self):
        with self.factory() as session:
            return [dto(row) for row in session.scalars(select(Order).order_by(Order.created_at.desc()))]

    def refund_order(self, actor_id, order_id, reason, request_key):
        actor_id = actor_text(actor_id)
        reason_text(reason)
        globals()['request_key'](request_key)
        with self.factory.begin() as session:
            original = session.get(Order, order_id)
            if original is None:
                raise DomainError('Order not found')
            user = self._user(session, original.user_id, True)
            order = session.scalar(select(Order).where(Order.id == order_id).with_for_update())
            reference = 'refund:' + order_id
            previous = session.scalar(select(Ledger).where(Ledger.reference == reference))
            if previous:
                return {'order_id': order_id, 'status': 'refunded', 'balance_units': previous.after_units}
            self._ledger(session, user, order.total_units, reference, reason, actor_id)
            order.status = 'refunded'
            deliveries = session.scalars(select(Outbox).where(
                Outbox.topic.in_(['telegram_order', 'telegram_text', 'telegram_document']),
                Outbox.payload['order_id'].as_string() == order_id).with_for_update())
            for delivery in deliveries:
                if delivery.status != 'done':
                    delivery.status = 'done'
                    delivery.lease_token = None
                    delivery.last_error = 'Cancelled: order refunded'
            session.add(Audit(actor_id=actor_id, action='refund_order', details={
                'order_id': order_id, 'reason': reason, 'request_key': request_key}))
            return {'order_id': order_id, 'status': 'refunded', 'balance_units': user.balance_units}

    def review_payment(self, actor_id, transaction_id, user_id, reason, request_key):
        actor_id = actor_text(actor_id)
        reason_text(reason)
        globals()['request_key'](request_key)
        with self.factory.begin() as session:
            user = self._user(session, user_id, True)
            payment = session.scalar(select(Payment).where(Payment.transaction_id == transaction_id).with_for_update())
            if payment is None or payment.currency != 'USDT' or payment.amount_units <= 0:
                raise DomainError('Payment cannot be credited')
            reference = 'payment:' + transaction_id
            previous = session.scalar(select(Ledger).where(Ledger.reference == reference))
            if previous:
                if previous.user_id != user_id:
                    raise DomainError('Payment already belongs to another user')
                return {'status': 'paid', 'user_id': user_id, 'balance_units': previous.after_units}
            if payment.status != 'needs_review':
                raise DomainError('Payment has already been processed')
            candidate = session.scalar(select(Topup).where(Topup.expected_units == payment.amount_units))
            if candidate is not None and candidate.user_id != user_id:
                raise DomainError('Reserved payment belongs to another user')
            if candidate is not None:
                candidate = session.scalar(select(Topup).where(Topup.id == candidate.id).with_for_update()
                                           .execution_options(populate_existing=True))
            if candidate is not None and candidate.status == 'paid':
                raise DomainError('This reserved amount has already been credited')
            self._ledger(session, user, payment.amount_units, reference, reason, actor_id)
            payment.status = 'paid'
            if candidate:
                candidate.status = 'paid'
                payment.topup_id = candidate.id
            payload = {'topup_id': candidate.id if candidate else transaction_id, 'user_id': user_id,
                       'amount_units': payment.amount_units, 'balance_units': user.balance_units}
            self._enqueue(session, 'telegram_topup', payload, 'telegram_review:' + transaction_id)
            self._enqueue(session, 'discord_topup', payload, 'discord_review:' + transaction_id)
            session.add(Audit(actor_id=actor_id, action='review_payment', details={
                'transaction_id': transaction_id, 'user_id': user_id, 'reason': reason, 'request_key': request_key}))
            return {'status': 'paid', 'user_id': user_id, 'balance_units': user.balance_units}

    def get_order(self, user_id, order_id):
        with self.factory() as session:
            order = session.get(Order, order_id)
            if order is None or order.user_id != user_id:
                raise DomainError('Order not found')
            return self._order(session, order)

    def history(self, user_id):
        with self.factory() as session:
            self._user(session, user_id)
            return {'orders': [dto(row) for row in session.scalars(select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc()))],
                    'ledger': [dto(row) for row in session.scalars(select(Ledger).where(Ledger.user_id == user_id).order_by(Ledger.id.desc()))],
                    'topups': [dto(row) for row in session.scalars(select(Topup).where(Topup.user_id == user_id).order_by(Topup.created_at.desc()))]}

    def request_topup(self, user_id, base_units):
        money(base_units, True)
        if base_units % 1_000_000 or base_units > 10000 * UNITS:
            raise DomainError('Topup base must have at most two decimals and be at most 10000 USDT')
        now = utcnow()
        with self.factory.begin() as session:
            self._user(session, user_id, True)
            active = list(session.scalars(select(Topup).where(Topup.user_id == user_id, Topup.status == 'pending').with_for_update()))
            for row in active:
                if aware(row.expires_at) > now:
                    return dto(row)
                row.status = 'expired'
            latest = session.scalar(select(Topup).where(Topup.user_id == user_id)
                                    .order_by(Topup.created_at.desc()).limit(1))
            if latest and (now - aware(latest.created_at)).total_seconds() < self.topup_cooldown_seconds:
                raise DomainError('Please wait 60 seconds before creating another topup request')
            recent_count = session.scalar(select(func.count()).select_from(Topup).where(
                Topup.user_id == user_id, Topup.status != 'paid', Topup.created_at > now - timedelta(hours=24)))
            if recent_count >= self.topup_daily_limit:
                raise DomainError('Topup request limit reached; try again after 24 hours')
            count = 99 if self.precision == 4 else 9
            choices = list(range(1, count + 1))
            while choices:
                suffix = choices.pop(secrets.randbelow(len(choices)))
                expected = base_units + suffix * (10 ** (8 - self.precision))
                topup_id = str(uuid4())
                if insert_once(session, AmountLease, {'amount_units': expected, 'topup_id': topup_id}, 'amount_units'):
                    row = Topup(id=topup_id, user_id=user_id, base_units=base_units, expected_units=expected,
                                status='pending', created_at=now, expires_at=now + timedelta(seconds=self.topup_ttl_seconds))
                    session.add(row)
                    session.flush()
                    return dto(row)
            raise DomainError('No unique payment amounts available; choose another base amount')

    def cancel_topup(self, user_id, topup_id):
        with self.factory.begin() as session:
            self._user(session, user_id, True)
            row = session.scalar(select(Topup).where(Topup.id == topup_id, Topup.user_id == user_id).with_for_update())
            if row is None:
                raise DomainError('Topup not found')
            if row.status == 'pending':
                row.status = 'cancelled'
            return dto(row)

    def list_topups(self):
        with self.factory() as session:
            return [dto(row) for row in session.scalars(select(Topup).order_by(Topup.created_at.desc()))]

    def list_payments(self):
        with self.factory() as session:
            return [dto(row) for row in session.scalars(select(Payment).order_by(Payment.occurred_at.desc()))]

    def _mark_order_delivered(self, session, order_id):
        order = session.scalar(select(Order).where(Order.id == order_id).with_for_update())
        if order is None or order.status == 'refunded':
            return
        rows = list(session.scalars(select(Outbox).where(
            Outbox.topic.in_(['telegram_order', 'telegram_text', 'telegram_document']),
            Outbox.payload['order_id'].as_string() == order_id)))
        parts = [row for row in rows if row.topic != 'telegram_order']
        if parts and all(row.status == 'done' for row in rows):
            order.status = 'delivered'

    def mark_order_delivered(self, order_id):
        with self.factory.begin() as session:
            self._mark_order_delivered(session, order_id)

    def record_payment(self, transaction_id, amount_units, currency, occurred_at, receiver_id='', order_type='C2C'):
        if not isinstance(transaction_id, str) or not transaction_id or len(transaction_id) > 256:
            raise DomainError('Invalid payment transaction ID')
        money(amount_units)
        if not isinstance(occurred_at, datetime) or occurred_at.tzinfo is None:
            raise DomainError('Payment time must include timezone')
        if not isinstance(currency, str) or len(currency) > 20 or len(receiver_id) > 160 or len(order_type) > 30:
            raise DomainError('Invalid payment metadata')
        currency, occurred_at = currency.upper(), aware(occurred_at)
        with self.factory.begin() as session:
            candidate = session.scalar(select(Topup).where(Topup.expected_units == amount_units)) if currency == 'USDT' and amount_units > 0 else None
            user = self._user(session, candidate.user_id, True) if candidate else None
            if candidate:
                candidate = session.scalar(select(Topup).where(Topup.id == candidate.id).with_for_update()
                                           .execution_options(populate_existing=True))
            inserted = insert_once(session, Payment, {'transaction_id': transaction_id, 'amount_units': amount_units,
                        'currency': currency, 'receiver_id': receiver_id, 'order_type': order_type,
                        'occurred_at': occurred_at, 'status': 'needs_review'}, 'transaction_id')
            payment = session.get(Payment, transaction_id)
            if not inserted:
                return {'status': payment.status, 'topup_id': payment.topup_id}
            if (candidate and candidate.status in ('pending', 'expired')
                    and aware(candidate.created_at) <= occurred_at <= aware(candidate.expires_at)):
                self._ledger(session, user, amount_units, 'payment:' + transaction_id, 'USDT topup')
                candidate.status = 'paid'
                payment.status, payment.topup_id = 'paid', candidate.id
                payload = {'topup_id': candidate.id, 'user_id': user.id, 'amount_units': amount_units,
                           'balance_units': user.balance_units}
                self._enqueue(session, 'telegram_topup', payload, 'telegram_topup:' + candidate.id)
                self._enqueue(session, 'discord_topup', payload, 'discord_topup:' + candidate.id)
            return {'status': payment.status, 'topup_id': payment.topup_id}

    def get_checkpoint(self, name):
        with self.factory() as session:
            row = session.get(Checkpoint, name)
            return aware(row.value) if row else None

    def set_checkpoint(self, name, value):
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise DomainError('Checkpoint must include timezone')
        with self.factory.begin() as session:
            insert_once(session, Checkpoint, {'name': name, 'value': value}, 'name')
            row = session.scalar(select(Checkpoint).where(Checkpoint.name == name).with_for_update())
            if aware(value) > aware(row.value):
                row.value = value

    def _enqueue(self, session, topic, payload, dedupe_key):
        insert_once(session, Outbox, {'topic': topic, 'payload': dict(payload), 'dedupe_key': dedupe_key,
                    'status': 'pending', 'attempts': 0, 'available_at': utcnow(), 'last_error': ''}, 'dedupe_key')

    def enqueue(self, topic, payload, dedupe_key):
        if not isinstance(topic, str) or len(topic) > 60 or not isinstance(dedupe_key, str) or len(dedupe_key) > 300:
            raise DomainError('Invalid notification metadata')
        with self.factory.begin() as session:
            self._enqueue(session, topic, payload, dedupe_key)

    def claim_outbox(self, limit=20):
        now = utcnow()
        with self.factory.begin() as session:
            rows = list(session.scalars(select(Outbox).where(Outbox.status != 'done', Outbox.available_at <= now)
                        .order_by(Outbox.id).limit(limit).with_for_update(skip_locked=True)))
            for row in rows:
                row.status = 'processing'
                row.attempts += 1
                row.available_at = now + timedelta(seconds=self.outbox_lease_seconds)
                row.lease_token = str(uuid4())
            return [dto(row) for row in rows]

    def finish_outbox(self, id, success, error='', retry_seconds=30, lease_token=None):
        with self.factory.begin() as session:
            initial = session.get(Outbox, id)
            if initial is None:
                raise DomainError('Notification not found')
            if initial.topic in ('telegram_order', 'telegram_text', 'telegram_document'):
                session.scalar(select(Order).where(Order.id == initial.payload.get('order_id')).with_for_update())
            row = session.scalar(select(Outbox).where(Outbox.id == id).with_for_update()
                                 .execution_options(populate_existing=True))
            if row is None:
                raise DomainError('Notification not found')
            if row.status == 'done':
                return False
            if (row.status != 'processing' or not lease_token or row.lease_token != lease_token
                    or aware(row.available_at) <= utcnow()):
                return False
            row.status = 'done' if success else 'pending'
            row.lease_token = None
            row.last_error = '' if success else 'Delivery failed; retry scheduled'
            row.available_at = utcnow() + timedelta(seconds=max(0, min(retry_seconds, 86400)))
            if success and row.topic in ('telegram_order', 'telegram_text', 'telegram_document'):
                session.flush()
                self._mark_order_delivered(session, row.payload.get('order_id'))
            return True
