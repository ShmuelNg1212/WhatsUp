from django.contrib import admin

from .models import Comment, Like, Post


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    raw_id_fields = ("author",)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "short_body", "has_image", "created_at")
    list_select_related = ("author",)
    search_fields = ("body", "author__username")
    raw_id_fields = ("author",)
    inlines = [CommentInline]

    @admin.display(description="Body")
    def short_body(self, obj):
        return obj.body[:60]

    @admin.display(boolean=True, description="Image")
    def has_image(self, obj):
        return bool(obj.image)


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ("user", "post", "created_at")
    list_select_related = ("user", "post")
    raw_id_fields = ("user", "post")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("author", "post", "body", "created_at")
    list_select_related = ("author", "post")
    raw_id_fields = ("author", "post")
