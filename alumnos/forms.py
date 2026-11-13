import unicodedata
from pathlib import Path
from PIL import Image, UnidentifiedImageError

from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import (
    MinimumLengthValidator, NumericPasswordValidator,
    validate_password, password_validators_help_text_html,
)

from .models import Alumno

# Política específica del registro de alumnos.
VALIDADORES_PASSWORD = [MinimumLengthValidator(min_length=8), NumericPasswordValidator()]


class CantidadCarritoForm(forms.Form):
    cantidad = forms.IntegerField(min_value=1, max_value=99, label='Cantidad')


class ConfirmarCompraForm(forms.Form):
    numero = forms.UUIDField(widget=forms.HiddenInput)
    resumen = forms.CharField(widget=forms.HiddenInput)
    comprobante = forms.FileField(label='Comprobante de pago', widget=forms.FileInput(attrs={
        'accept': '.jpg,.jpeg,.png,.webp,.pdf', 'aria-describedby': 'comprobante-ayuda',
    }))

    def clean_comprobante(self):
        archivo = self.cleaned_data['comprobante']
        if archivo.size > 5 * 1024 * 1024:
            raise forms.ValidationError('El comprobante no puede superar 5 MB.')
        extension = Path(archivo.name).suffix.lower()
        try:
            if extension == '.pdf':
                contenido = archivo.read()
                if not contenido.startswith(b'%PDF-') or b'%%EOF' not in contenido[-1024:]:
                    raise forms.ValidationError('El archivo no tiene un formato PDF válido.')
            elif extension in ('.jpg', '.jpeg', '.png', '.webp'):
                imagen = Image.open(archivo)
                formatos = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.webp': 'WEBP'}
                if imagen.format != formatos[extension]:
                    raise forms.ValidationError('La imagen no corresponde al formato indicado.')
                imagen.verify()
            else:
                raise forms.ValidationError('Selecciona una imagen JPG, PNG, WebP o un PDF.')
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            raise forms.ValidationError('No se pudo leer la imagen. Selecciona otra.')
        finally:
            archivo.seek(0)
        return archivo


class RegistroAlumnoForm(forms.ModelForm):
    matricula = forms.RegexField(
        regex=r'\A[0-9]{8}\Z', strip=False,
        label='Matrícula', help_text='Exactamente 8 dígitos. Conserva los ceros iniciales.',
        error_messages={
            'invalid': 'La matrícula debe contener exactamente 8 dígitos (0–9).',
        },
        widget=forms.TextInput(attrs={
            'autocomplete': 'off', 'inputmode': 'numeric', 'pattern': '[0-9]{8}',
            'minlength': '8', 'maxlength': '8', 'title': 'Introduce exactamente 8 dígitos (0–9).',
        }),
    )
    password = forms.CharField(label='Contraseña', strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}), help_text=password_validators_help_text_html(VALIDADORES_PASSWORD))
    confirmar_password = forms.CharField(label='Confirmar contraseña', strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))

    class Meta:
        model = Alumno
        fields = ['nombre', 'apellido_paterno', 'apellido_materno', 'correo', 'password', 'confirmar_password', 'matricula', 'foto']
        labels = {'nombre': 'Nombre', 'apellido_paterno': 'Apellido paterno', 'apellido_materno': 'Apellido materno', 'correo': 'Correo electrónico', 'foto': 'Foto de perfil'}
        help_texts = {'apellido_materno': 'Opcional.', 'foto': 'Opcional. JPG, PNG o WebP, máximo 5 MB.'}
        widgets = {'correo': forms.EmailInput(attrs={'autocomplete': 'email'}), 'foto': forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'})}

    def clean(self):
        data = super().clean()
        for campo in ('nombre', 'apellido_paterno', 'apellido_materno'):
            valor = unicodedata.normalize('NFC', ' '.join(data.get(campo, '').split()))
            if valor and (not any(c.isalpha() for c in valor) or not all(c.isalpha() or c in " '-’" for c in valor)):
                self.add_error(campo, 'Usa letras, espacios, apóstrofos o guiones.')
            elif not valor and campo != 'apellido_materno' and campo not in self.errors:
                self.add_error(campo, 'Este campo es obligatorio.')
            else:
                data[campo] = valor
        password = data.get('password')
        if password:
            user = get_user_model()(first_name=data.get('nombre', ''), last_name=data.get('apellido_paterno', ''), email=data.get('correo', ''), username=data.get('correo', ''))
            try:
                validate_password(password, user, password_validators=VALIDADORES_PASSWORD)
            except forms.ValidationError as error:
                self.add_error('password', error)
        if password and data.get('confirmar_password') and password != data['confirmar_password']:
            self.add_error('confirmar_password', 'Las contraseñas no coinciden.')
        return data

    def clean_correo(self):
        correo = self.cleaned_data['correo'].strip().lower()
        if Alumno.objects.filter(correo__iexact=correo).exists() or get_user_model().objects.filter(email__iexact=correo).exists():
            raise forms.ValidationError('Ya existe una cuenta con este correo.')
        return correo

    def clean_matricula(self):
        matricula = self.cleaned_data['matricula']
        if Alumno.objects.filter(matricula__iexact=matricula).exists():
            raise forms.ValidationError('Esta matrícula ya está registrada.')
        return matricula

    def clean_foto(self):
        foto = self.cleaned_data.get('foto')
        if foto:
            if foto.size > 5 * 1024 * 1024:
                raise forms.ValidationError('La foto no puede superar 5 MB.')
            if foto.image.format not in ('JPEG', 'PNG', 'WEBP'):
                raise forms.ValidationError('Selecciona una imagen JPG, PNG o WebP.')
        return foto


class LoginAlumnoForm(forms.Form):
    correo = forms.EmailField(label='Correo electrónico', max_length=254, widget=forms.EmailInput(attrs={'autocomplete': 'username', 'autofocus': True}))
    password = forms.CharField(label='Contraseña', strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}))

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.usuario = None

    def clean(self):
        data = super().clean()
        if data.get('correo') and data.get('password'):
            alumno = Alumno.objects.select_related('usuario').filter(correo__iexact=data['correo'].strip()).first()
            username = alumno.usuario.username if alumno else '__alumno_inexistente__'
            usuario = authenticate(self.request, username=username, password=data['password'])
            if not alumno or not usuario or usuario.is_staff or usuario.is_superuser:
                raise forms.ValidationError('El correo o la contraseña no son correctos.')
            self.usuario = usuario
        return data
