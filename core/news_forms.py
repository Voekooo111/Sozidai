from django import forms

from .models import News, NewsImage, validate_news_image_size


class MultiImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True
class MultiImageField(forms.FileField):
    widget = MultiImageInput
    def clean(self, data, initial=None):
        if not data: return []
        if not isinstance(data, (list, tuple)): data = [data]
        return [super(MultiImageField, self).clean(item, initial) for item in data]
class NewsForm(forms.ModelForm):
    images = MultiImageField(required=False, label="Фотографии новости", validators=[validate_news_image_size], widget=MultiImageInput(attrs={"accept":"image/*", "multiple":True, "data-news-files":""}))
    class Meta:
        model = News
        fields = ["title", "content", "priority", "delete_on"]
        widgets = {
            "content": forms.Textarea(attrs={"rows": 12}),
            "image": forms.FileInput(attrs={"accept": "image/*", "data-max-mb": 5}),
            "delete_on": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["delete_on"].input_formats = ["%Y-%m-%d"]
