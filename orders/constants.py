UNIT_CHOICES = [
    ('piece', 'Dona'),
    ('kg', 'Kilogramm'),
    ('g', 'Gramm'),
    ('pack', 'Paket'),
    ('liter', 'Litr'),
    ('ton', 'Tonna'),
    ('meter', 'Metr'),
    ('box', 'Quti'),
]

UNIT_LABELS = dict(UNIT_CHOICES)


class OrderStatus:
    DRAFT = 'DRAFT'
    SUBMITTED = 'SUBMITTED'
    ACCEPTED = 'ACCEPTED'
    DECLINED = 'DECLINED'
    IN_SHIPMENT = 'IN_SHIPMENT'
    DELIVERED = 'DELIVERED'
    CHOICES = [
        ('DRAFT', 'Qoralama'),
        ('SUBMITTED', 'Yuborildi'),
        ('ACCEPTED', 'Qabul qilindi'),
        ('DECLINED', 'Rad etildi'),
        ('IN_SHIPMENT', "Jo'natmada"),
        ('DELIVERED', 'Yetkazildi'),
    ]
    ACTIVE = [SUBMITTED, ACCEPTED, IN_SHIPMENT]
    CLOSED = [DELIVERED, DECLINED]


class ShipmentStatus:
    PREPARING = 'PREPARING'
    DISPATCHED = 'DISPATCHED'
    DELIVERED = 'DELIVERED'
    CHOICES = [
        ('PREPARING', 'Tayyorlanmoqda'),
        ('DISPATCHED', "Yo'lda"),
        ('DELIVERED', 'Yetkazildi'),
    ]


class DeliveryStatus:
    PENDING = 'PENDING'
    DISPATCHED = 'DISPATCHED'
    DELIVERED = 'DELIVERED'
    CHOICES = [
        ('PENDING', 'Kutilmoqda'),
        ('DISPATCHED', "Yo'lda"),
        ('DELIVERED', 'Yetkazildi'),
    ]
    # Valid forward transitions
    TRANSITIONS = {
        PENDING: [DISPATCHED, DELIVERED],
        DISPATCHED: [DELIVERED],
        DELIVERED: [],
    }


class PaymentStatus:
    PENDING = 'PENDING'
    PAID = 'PAID'
    CHOICES = [
        ('PENDING', "To'lanmagan"),
        ('PAID', "To'langan"),
    ]


class InvoiceType:
    ORDER = 'ORDER'
    CHOICES = [
        ('ORDER', 'Buyurtma'),
    ]


MAX_IMAGE_SIZE_MB = 5
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024
ALLOWED_IMAGE_MIME_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
