from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import Comida, HorarioPedidos, separar_ingredientes

MAX_INGREDIENTES = 30
MAX_LARGO_INGREDIENTE = 60


class HorarioPedidosForm(forms.ModelForm):
    hora_inicio = forms.TimeField(label='Inicio del registro', input_formats=['%H:%M'],
                                  widget=forms.TimeInput(format='%H:%M', attrs={'type': 'time', 'step': '60'}))
    hora_fin = forms.TimeField(label='Fin del registro', input_formats=['%H:%M'],
                               widget=forms.TimeInput(format='%H:%M', attrs={'type': 'time', 'step': '60'}))

    class Meta:
        model = HorarioPedidos
        fields = ['hora_inicio', 'hora_fin']

    def clean(self):
        datos = super().clean()
        if datos.get('hora_inicio') is not None and datos.get('hora_inicio') == datos.get('hora_fin'):
            self.add_error('hora_fin', 'La hora de fin debe ser distinta de la hora de inicio.')
        return datos


class LoginComedorForm(AuthenticationForm):
    """Login del comedor. Solo entra la cuenta del comedor (is_staff), no las de clientes."""

    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': 'El nombre o la contraseña no son correctos.',
    }

    username = forms.CharField(
        label='Nombre',
        widget=forms.TextInput(attrs={'autofocus': True, 'autocomplete': 'username'}),
    )
    password = forms.CharField(
        label='Contraseña',
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
    )

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise forms.ValidationError(
                'Esta cuenta no tiene acceso al comedor.',
                code='sin_acceso',
            )


class ComidaForm(forms.ModelForm):
    class Meta:
        model = Comida
        fields = ['nombre', 'ingredientes', 'precio', 'imagen']
        labels = {
            'nombre': 'Nombre de la comida',
            'ingredientes': 'Ingredientes',
            'precio': 'Precio',
            'imagen': 'Foto',
        }
        widgets = {
            'nombre': forms.TextInput(attrs={
                'placeholder': 'Ej. Enchiladas verdes', 'autocomplete': 'off',
            }),
            # Con JavaScript se maneja como etiquetas; sin JavaScript queda como texto (uno por línea).
            'ingredientes': forms.Textarea(attrs={'rows': 4}),
            'precio': forms.NumberInput(attrs={
                'step': '0.50', 'min': '0.01', 'inputmode': 'decimal', 'placeholder': '0.00',
            }),
            'imagen': forms.FileInput(attrs={'accept': 'image/*', 'class': 'sr-only'}),
        }
        error_messages = {
            'ingredientes': {'required': 'Agrega al menos un ingrediente.'},
        }

    def clean_ingredientes(self):
        """Guarda los ingredientes limpios, uno por línea y sin repetidos."""
        lista = separar_ingredientes(self.cleaned_data['ingredientes'])
        if not lista:
            raise forms.ValidationError('Agrega al menos un ingrediente.')
        if len(lista) > MAX_INGREDIENTES:
            raise forms.ValidationError(f'Son demasiados ingredientes (máximo {MAX_INGREDIENTES}).')
        if any(len(ingrediente) > MAX_LARGO_INGREDIENTE for ingrediente in lista):
            raise forms.ValidationError(
                f'Cada ingrediente puede tener máximo {MAX_LARGO_INGREDIENTE} caracteres.'
            )
        return '\n'.join(lista)
