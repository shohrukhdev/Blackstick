import logging
from decimal import Decimal

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from orders.constants import ALLOWED_IMAGE_MIME_TYPES, MAX_IMAGE_SIZE_BYTES, MAX_IMAGE_SIZE_MB, OrderStatus
from orders.models import Category, Item, Order, Supplier

logger = logging.getLogger(__name__)


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'display_order']
        labels = {
            'name': 'Nomi',
            'display_order': 'Tartib raqami',
        }
        help_texts = {
            'display_order': 'Kichik raqam — yuqorida ko\'rinadi',
        }
        widgets = {
            'display_order': forms.NumberInput(attrs={'min': 0}),
        }


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['category', 'name', 'description', 'unit', 'base_price', 'profit', 'image', 'is_active']
        labels = {
            'category': 'Kategoriya',
            'name': 'Nomi',
            'description': 'Tavsif',
            'unit': "O'lchov birligi",
            'base_price': 'Xarid narxi (so\'m)',
            'profit': 'Foyda (so\'m)',
            'image': 'Rasm',
            'is_active': 'Faol',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'base_price': forms.NumberInput(attrs={'min': 0, 'step': '0.01'}),
            'profit': forms.NumberInput(attrs={'min': 0, 'step': '0.01'}),
        }

    def __init__(self, supplier, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(supplier=supplier)
        self.fields['category'].required = False
        self.fields['category'].empty_label = '— Kategoriyasiz —'
        self.fields['description'].required = False
        # Image is required for new items only; keep existing image on edit
        instance = kwargs.get('instance')
        if instance and instance.pk and instance.image:
            self.fields['image'].required = False
            self.fields['image'].help_text = 'Yangi rasm yuklamasangiz, mavjudi saqlanadi.'

    def clean_image(self):  # noqa: E301
        image = self.cleaned_data.get('image')
        if image and hasattr(image, 'size') and image.size > 0:
            if image.size > MAX_IMAGE_SIZE_BYTES:
                raise forms.ValidationError(
                    f'Rasm hajmi {MAX_IMAGE_SIZE_MB} MB dan oshmasligi kerak.'
                )
            content_type = getattr(image, 'content_type', None)
            if content_type and content_type not in ALLOWED_IMAGE_MIME_TYPES:
                raise forms.ValidationError('Faqat JPEG, PNG va WebP formatlar qabul qilinadi.')
        return image


# ── Client forms ───────────────────────────────────────────────────────────


class _PasswordMixin:
    """Shared password + confirm logic for client registration forms."""

    def clean_password(self):
        password = self.cleaned_data.get('password', '')
        try:
            validate_password(password)
        except DjangoValidationError as e:
            raise forms.ValidationError(list(e.messages))
        return password

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password') != cleaned.get('password_confirm'):
            self.add_error('password_confirm', "Parollar mos kelmadi.")
        return cleaned


class ClientCreateForm(_PasswordMixin, forms.Form):
    company_name = forms.CharField(max_length=255, label='Kompaniya nomi')
    full_name = forms.CharField(max_length=150, label="To'liq ism")
    phone = forms.CharField(max_length=30, label='Telefon raqami')
    email = forms.EmailField(required=False, label='Email (ixtiyoriy)')
    password = forms.CharField(widget=forms.PasswordInput, label='Parol')
    password_confirm = forms.CharField(widget=forms.PasswordInput, label='Parolni takrorlang')


class InviteRegisterForm(_PasswordMixin, forms.Form):
    company_name = forms.CharField(max_length=255, label='Kompaniya nomi')
    full_name = forms.CharField(max_length=150, label="To'liq ismingiz")
    phone = forms.CharField(max_length=30, label='Telefon raqami')
    password = forms.CharField(widget=forms.PasswordInput, label='Parol')
    password_confirm = forms.CharField(widget=forms.PasswordInput, label='Parolni takrorlang')


# ── Payment forms ──────────────────────────────────────────────────────────

_INPUT_CLASS = (
    'w-full rounded-xl border border-gray-300 px-3.5 py-2.5 text-sm focus:outline-none '
    'focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-shadow'
)


_ORDER_STATUS_LABELS = {
    'ACCEPTED': 'Qabul qilingan',
    'IN_SHIPMENT': "Jo'natmada",
    'DELIVERED': 'Yetkazildi',
}


class _OrderChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        date_str = obj.submitted_at.strftime('%d.%m.%Y') if obj.submitted_at else '—'
        status = _ORDER_STATUS_LABELS.get(obj.status, obj.status)
        return f'#{obj.pk} — {date_str} ({status})'


class PaymentRecordForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal('0.01'),
        label="Miqdor (so'm)",
        widget=forms.NumberInput(attrs={'class': _INPUT_CLASS, 'min': '1', 'step': '1'}),
    )
    date = forms.DateField(
        label='Sana',
        widget=forms.DateInput(attrs={'class': _INPUT_CLASS, 'type': 'date'}),
    )
    notes = forms.CharField(
        max_length=500, required=False, label='Izoh',
        widget=forms.Textarea(attrs={'class': _INPUT_CLASS, 'rows': '2'}),
    )
    order = _OrderChoiceField(
        queryset=Order.objects.none(), required=False,
        label="Buyurtma (ixtiyoriy)",
        empty_label="— Tanlanmagan —",
        widget=forms.Select(attrs={'class': _INPUT_CLASS}),
    )

    def __init__(self, supplier, client, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['order'].queryset = (
            Order.objects
            .filter(
                supplier=supplier, client=client,
                status__in=[OrderStatus.ACCEPTED, OrderStatus.IN_SHIPMENT, OrderStatus.DELIVERED],
            )
            .order_by('-submitted_at')
        )


# ── Client edit form ──────────────────────────────────────────────────────


class ClientEditForm(forms.Form):
    company_name = forms.CharField(
        max_length=255, label='Kompaniya nomi',
        widget=forms.TextInput(attrs={'class': _INPUT_CLASS}),
    )
    phone = forms.CharField(
        max_length=30, label='Telefon raqami',
        widget=forms.TextInput(attrs={'class': _INPUT_CLASS}),
    )
    email = forms.EmailField(
        required=False, label='Email',
        widget=forms.EmailInput(attrs={'class': _INPUT_CLASS}),
    )
    address = forms.CharField(
        max_length=500, required=False, label='Manzil',
        widget=forms.Textarea(attrs={'class': _INPUT_CLASS, 'rows': '2'}),
    )
    latitude = forms.DecimalField(
        max_digits=10, decimal_places=8, required=False,
        min_value=-90, max_value=90,
        label='Kenglik (Latitude)',
        widget=forms.NumberInput(attrs={'class': _INPUT_CLASS, 'step': 'any', 'placeholder': '41.29950000'}),
    )
    longitude = forms.DecimalField(
        max_digits=11, decimal_places=8, required=False,
        min_value=-180, max_value=180,
        label='Uzunlik (Longitude)',
        widget=forms.NumberInput(attrs={'class': _INPUT_CLASS, 'step': 'any', 'placeholder': '69.24007000'}),
    )
    telegram_id = forms.IntegerField(
        required=False, label='Telegram ID',
        widget=forms.NumberInput(attrs={'class': _INPUT_CLASS, 'placeholder': '123456789'}),
    )

    def __init__(self, *args, client_pk=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._client_pk = client_pk

    def clean(self):
        cleaned = super().clean()
        lat = cleaned.get('latitude')
        lng = cleaned.get('longitude')
        if (lat is None) != (lng is None):
            raise forms.ValidationError("Kenglik va uzunlik ikkalasi ham kiritilishi kerak.")
        return cleaned

    def clean_telegram_id(self):
        from orders.models import Client
        telegram_id = self.cleaned_data.get('telegram_id')
        if telegram_id is not None:
            qs = Client.objects.filter(telegram_id=telegram_id)
            if self._client_pk:
                qs = qs.exclude(pk=self._client_pk)
            if qs.exists():
                raise forms.ValidationError("Bu Telegram ID allaqachon boshqa mijozda ro'yxatdan o'tgan.")
        return telegram_id


# ── Supplier profile form ─────────────────────────────────────────────────


class SupplierProfileForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['business_name', 'phone', 'address', 'logo']
        labels = {
            'business_name': 'Biznes nomi',
            'phone': 'Telefon raqami',
            'address': 'Manzil',
            'logo': 'Logo',
        }
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['address'].required = False
        self.fields['logo'].required = False
        if self.instance and self.instance.pk and self.instance.logo:
            self.fields['logo'].help_text = 'Yangi rasm yuklamasangiz, mavjudi saqlanadi.'

    def clean_logo(self):
        logo = self.cleaned_data.get('logo')
        if logo and hasattr(logo, 'size') and logo.size > 0:
            if logo.size > MAX_IMAGE_SIZE_BYTES:
                raise forms.ValidationError(
                    f'Rasm hajmi {MAX_IMAGE_SIZE_MB} MB dan oshmasligi kerak.'
                )
            content_type = getattr(logo, 'content_type', None)
            if content_type and content_type not in ALLOWED_IMAGE_MIME_TYPES:
                raise forms.ValidationError('Faqat JPEG, PNG va WebP formatlar qabul qilinadi.')
        return logo


# ── Expense forms ──────────────────────────────────────────────────────────


class ExpenseForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal('1'),
        label="Miqdor (so'm)",
        widget=forms.NumberInput(attrs={'class': _INPUT_CLASS, 'min': '1', 'step': '1',
                                        'placeholder': '0'}),
    )
    date = forms.DateField(
        label='Sana',
        widget=forms.DateInput(attrs={'class': _INPUT_CLASS, 'type': 'date'}),
    )
    notes = forms.CharField(
        max_length=500, label='Izoh',
        widget=forms.TextInput(attrs={'class': _INPUT_CLASS, 'placeholder': 'Xarajat tavsifi'}),
    )
