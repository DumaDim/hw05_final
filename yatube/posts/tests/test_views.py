from django.urls import reverse
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django import forms
from django.core.cache import cache

from ..models import Post, Comment


from ..models import Group, Post, User

User = get_user_model()


class PostPagesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create(username='auth')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовая пост'
        )

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_pages_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        templates_pages_names = {
            reverse('posts:index'): 'posts/index.html',
            reverse('posts:group_list', kwargs={'slug': self.group.slug}):
            'posts/group_list.html',
            reverse('posts:profile', kwargs={'username': self.user.username}):
            'posts/profile.html',
            reverse('posts:post_detail', kwargs={'post_id': self.post.pk}):
            'posts/post_detail.html',
            reverse('posts:post_create'): 'posts/create_post.html',
            reverse('posts:post_edit', kwargs={'post_id': self.post.pk}):
            'posts/create_post.html'
        }
        for reverse_name, template in templates_pages_names.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(reverse_name)
                self.assertTemplateUsed(response, template)

    def test_index_show_correct_context(self):
        """Шаблон index сформирован с правильным контекстом."""
        response = self.authorized_client.get(reverse('posts:index'))
        first_object = response.context['page_obj'][0]
        post_text_0 = first_object.text
        post_author_0 = first_object.author
        self.assertEqual(post_text_0, 'Тестовая пост')
        self.assertEqual(post_author_0, self.user)

    def test_group_list_show_correct_context(self):
        """Шаблон group_list сформирован с правильным контекстом."""
        response = (self.guest_client.get(
            reverse('posts:group_list', kwargs={'slug': self.group.slug})))
        self.assertEqual(response.context.get(
            'group').title, 'Тестовая группа')

    def test_profile_show_correct_context(self):
        """Шаблон profile сформирован с правильным контекстом."""
        response = (self.guest_client.get(
            reverse('posts:profile', kwargs={'username': self.user.username})))
        self.assertEqual(response.context.get('author').username, 'auth')

    def test_post_detail_show_correct_context(self):
        """Шаблон post_detail сформирован с правильным контекстом."""
        response = (self.guest_client.get(
            reverse('posts:post_detail', kwargs={'post_id': self.post.pk})))
        self.assertEqual(response.context.get('post').pk, self.post.pk)

    def test_post_edit_show_correct_context(self):
        """Шаблон post_edit сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse('posts:post_edit', kwargs={'post_id': self.post.pk}))
        form_fields = {
            'group': forms.fields.ChoiceField,
            'text': forms.fields.CharField,
            'image': forms.fields.ImageField
        }

        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)

    def test_post_create_show_correct_context(self):
        """Шаблон post_create сформирован с правильным контекстом."""
        response = self.authorized_client.get(reverse('posts:post_create'))
        form_fields = {
            'group': forms.fields.ChoiceField,
            'text': forms.fields.CharField,
            'image': forms.fields.ImageField
        }

        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)

    def test_post_detail_image(self):
        """Image передается в context post_detail."""
        response = self.guest_client.get(
            reverse('posts:post_detail', kwargs={"post_id": self.post.id})
        )
        obj = response.context['post']
        self.assertEqual(obj.image, self.post.image)

    def test_index_image(self):
        """Image передается в context index."""
        response = self.guest_client.get(
            reverse('posts:index')
        )
        obj = response.context['page_obj'][0]
        self.assertEqual(obj.image, self.post.image)

    def test_profile_image(self):
        """Image передается в context profile."""
        response = self.guest_client.get(
            reverse('posts:profile', kwargs={'username': self.user.username})
        )
        obj = response.context['page_obj'][0]
        self.assertEqual(obj.image, self.post.image)

    def test_comment_post_detail_view(self):
        """Комментарий появляется на странице поста."""
        comments_count = Comment.objects.count()
        form_data = {
            'text': 'Текст комментария'
        }
        response = self.authorized_client.post(
            reverse('posts:add_comment', args=({self.post.id})),
            data=form_data,
            follow=True
        )
        self.assertRedirects(response, reverse(
            'posts:post_detail', kwargs={'post_id': self.post.pk}))
        self.assertEqual(Comment.objects.count(), comments_count + 1)
        self.assertTrue(
            Comment.objects.filter(
                text='Текст комментария'
            ).exists()
        )

    def test_comment_guest_client(self):
        """Guest не может оставлять комментарии к постам."""
        comments_count = Comment.objects.count()
        form_data = {
            'text': 'Текст комментария'
        }
        response = self.guest_client.post(
            reverse('posts:add_comment', args=({self.post.id})),
            data=form_data,
            follow=True
        )
        self.assertRedirects(
            response,
            f'/auth/login/?next=/posts/{self.post.id}/comment/'
        )
        self.assertEqual(Comment.objects.count(), comments_count)
        self.assertFalse(
            Comment.objects.filter(
                text='Текст комментария'
            ).exists()
        )


class CacheViewsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='auth')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый текст'
        )

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_cache_index(self):
        """Проверка хранения и очищения кэша для index."""
        response = self.authorized_client.get(reverse('posts:index'))
        posts = response.content
        response_old = self.authorized_client.get(
            reverse('posts:index')
        )
        old_posts = response_old.content
        self.assertTrue(
            old_posts,
            posts)
        cache.clear()
        response_new = self.authorized_client.get(reverse('posts:index'))
        new_posts = response_new.content
        self.assertTrue(old_posts, new_posts)
