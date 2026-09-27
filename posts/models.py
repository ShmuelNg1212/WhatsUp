from django.conf import settings
from django.db import models
from django.urls import reverse

POST_MAX_LENGTH = 2000
COMMENT_MAX_LENGTH = 1000


class Post(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts"
    )
    body = models.TextField(max_length=POST_MAX_LENGTH)
    image = models.ImageField(upload_to="posts/%Y/%m/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(body=""),
                name="posts_post_body_not_empty",
                violation_error_message="A post needs some text.",
            ),
        ]
        indexes = [
            models.Index(fields=["author", "-created_at"], name="posts_post_author_recent_idx"),
            models.Index(fields=["-created_at"], name="posts_post_recent_idx"),
        ]

    def __str__(self):
        return f"{self.author}: {self.body[:40]}"

    def get_absolute_url(self):
        return reverse("posts:detail", args=[self.pk])


class Like(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="likes"
    )
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "post"],
                name="posts_like_once_per_user",
                violation_error_message="You already like this post.",
            ),
        ]
        indexes = [models.Index(fields=["post"], name="posts_like_post_idx")]

    def __str__(self):
        return f"{self.user} ♥ {self.post_id}"


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    body = models.TextField(max_length=COMMENT_MAX_LENGTH)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(body=""),
                name="posts_comment_body_not_empty",
                violation_error_message="A comment needs some text.",
            ),
        ]
        indexes = [
            models.Index(fields=["post", "created_at"], name="posts_comment_post_time_idx"),
        ]

    def __str__(self):
        return f"{self.author} on {self.post_id}: {self.body[:40]}"
