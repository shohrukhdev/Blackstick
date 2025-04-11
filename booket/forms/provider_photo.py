from django import forms
from django.core.exceptions import ValidationError

from booket.models import ProviderPhotos, Provider


class ProviderPhotosForm(forms.ModelForm):
    class Meta:
        model = ProviderPhotos
        fields = ['photo']
        widgets = {
            'photo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',  # Restrict to image files
            }),
            'DELETE': forms.CheckboxInput(attrs={'class': 'form-check-input'}),  # Style the delete checkbox

        }

    def clean_photo(


            self):
        photo = self.cleaned_data.get('photo')
        if photo:
            # Check file size (2 MB limit)
            max_size = 2 * 1024 * 1024  # 2 MB in bytes
            if photo.size > max_size:
                raise ValidationError("The file size must be less than 2 MB.")
        return photo


# Formset for multiple photos
ProviderPhotosFormSet = forms.inlineformset_factory(
    Provider,
    ProviderPhotos,
    form=ProviderPhotosForm,
    extra=1,  # Number of extra empty forms to display
    can_delete=True  # Allow deletion of existing photos
)
