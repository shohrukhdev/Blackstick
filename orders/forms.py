import logging

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from orders.constants import MAX_IMAGE_SIZE_BYTES, MAX_IMAGE_SIZE_MB, ALLOWED_IMAGE_MIME_TYPES
from orders.models import Category, Item

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
