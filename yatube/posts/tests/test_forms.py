import shutil
import tempfile

from http import HTTPStatus
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.cache import cache

from ..models import Follow, Group, Post, User

User = get_user_model()

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


class PostCreateFormTests(TestCase):
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

    def test_create_post(self):
        """Валидная форма создает запись в Post."""
        post_count = Post.objects.count()
        form_data = {
            'text': 'Тестовый текст',
            'group': self.group.id
        }
        response = self.authorized_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True
        )
        self.assertRedirects(response, reverse(
            'posts:profile', kwargs={'username': self.user.username}))
        self.assertEqual(Post.objects.count(), post_count + 1)
        self.assertTrue(
            Post.objects.filter(
                group=self.group.id,
                text='Тестовый текст'
            ).exists()
        )

    def test_post_edit(self):
        """Валидная форма изменяет пост."""
        post_count = Post.objects.count()
        form_data = {
            'text': 'Измененный текст'
        }
        response = self.authorized_client.post(
            reverse('posts:post_edit', args=({self.post.id})),
            data=form_data,
            follow=True
        )
        self.assertRedirects(response, reverse(
            'posts:post_detail', kwargs={'post_id': self.post.pk}))
        self.assertEqual(Post.objects.count(), post_count)
        self.assertTrue(
            Post.objects.filter(
                text='Измененный текст'
            ).exists()
        )

    def test_not_edit_post_guest(self):
        """Guest_client не редактирует посты."""
        post_count = Post.objects.count()
        form_data = {
            'text': 'Изменяем текст',
            'group': self.group.id
        }
        response = self.guest_client.post(
            reverse('posts:post_edit', args=({self.post.id})),
            data=form_data,
            follow=True
        )
        self.assertRedirects(response,
                             f'/auth/login/?next=/posts/{self.post.id}/edit/')
        self.assertEqual(Post.objects.count(), post_count)
        self.assertFalse(
            Post.objects.filter(
                text='Изменяем текст'
            ).exists()
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_not_create_post_guest(self):
        """Guest_client не создает запись в Post."""
        post_count = Post.objects.count()
        form_data = {
            'text': 'Тестовый текст',
            'group': self.group.id
        }
        response = self.guest_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True
        )
        self.assertRedirects(response,
                             '/auth/login/?next=/create/')
        self.assertEqual(Post.objects.count(), post_count)
        self.assertFalse(
            Post.objects.filter(
                text='Тестовый текст',
                group=self.group.id
            ).exists()
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostImageTests(TestCase):
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
            text='Тестовый текст',
            group=cls.group
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_image_context_profile(self):
        """Проверка image на создание в БД."""
        post_count = Post.objects.count()
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=small_gif,
            content_type='image/gif'
        )
        form_data = {
            'text': 'Тестовый текст',
            'group': self.group.id,
            'image': uploaded,
        }

        response = self.authorized_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True
        )

        self.assertRedirects(response,
                             reverse('posts:profile', kwargs={
                                 'username': self.user.username}))
        self.assertEqual(Post.objects.count(), post_count + 1)
        self.assertTrue(
            Post.objects.filter(
                group=self.group.id,
                text='Тестовый текст',
                image=self.post.image
            ).exists()
        )


class FollowViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.guest_client = Client()
        cls.author = User.objects.create_user(
            username='test_author'
        )
        cls.authorized_client = Client()
        cls.authorized_client.force_login(cls.author)

        cls.user_follow = User.objects.create_user(
            username='test_user_fol'
        )
        cls.authorized_user_follow_client = Client()
        cls.authorized_user_follow_client.force_login(
            cls.user_follow
        )

        cls.user_unfollow = User.objects.create_user(
            username='test_user_unfol'
        )
        cls.authorized_user_unfollow_client = Client()
        cls.authorized_user_unfollow_client.force_login(
            cls.user_unfollow
        )
        cls.group = Group.objects.create(
            title='test_group',
            slug='test-slug',
            description='test_description'
        )
        cls.post = Post.objects.create(
            text='test_post',
            group=cls.group,
            author=cls.author
        )

    def test_follow_authoriz_user(self):
        """Тест работы подписки авториз.пользователя на автора."""
        client = self.authorized_user_unfollow_client
        user = self.user_unfollow
        author = self.author
        follow_count = Follow.objects.count()
        form_data = {
            'user': user,
            'author': author
        }
        response = client.post(
            reverse('posts:profile_follow', args=[author.username]),
            data=form_data,
            follow=True
        )
        self.assertRedirects(response,
                             reverse('posts:profile', args=[author.username]))
        self.assertEqual(Follow.objects.count(), follow_count + 1)

    def test_unfollow(self):
        """Тест работы отписки от автора."""
        client = self.authorized_user_unfollow_client
        user = self.user_unfollow
        author = self.author
        client.get(
            reverse(
                'posts:profile_unfollow',
                args=[author.username]
            ),

        )
        follower = Follow.objects.filter(
            user=user,
            author=author
        ).exists()
        self.assertFalse(
            follower,
            'Не работает отписка от автора'
        )

    def test_guest_client_follow(self):
        """Guest_client не может подписаться на автора."""
        user = self.user_unfollow
        author = self.author
        follow_count = Follow.objects.count()
        form_data = {
            'user': user,
            'author': author
        }

        response = self.guest_client.post(
            reverse('posts:profile_follow', args=[author.username]),
            data=form_data,
            follow=True
        )
        self.assertRedirects(response,
                             f'/auth/login/?next=/profile/'
                             f'{author.username}/follow/')
        self.assertEqual(Follow.objects.count(), follow_count)

    def test_new_author_post_for_follower(self):
        """Новая запись в ленте подписчиков."""
        client = self.authorized_user_follow_client
        author = self.author
        group = self.group
        client.get(
            reverse(
                'posts:profile_follow',
                args=[author.username]
            )
        )
        response_old = client.get(
            reverse('posts:follow_index')
        )
        old_posts = response_old.context.get(
            'page_obj'
        ).object_list
        self.assertEqual(
            len(response_old.context.get('page_obj').object_list),
            1
        )
        self.assertIn(
            self.post,
            old_posts
        )
        new_post = Post.objects.create(
            text='test_new_post',
            group=group,
            author=author
        )
        cache.clear()
        response_new = client.get(
            reverse('posts:follow_index')
        )
        new_posts = response_new.context.get(
            'page_obj'
        ).object_list
        self.assertEqual(
            len(response_new.context.get('page_obj').object_list),
            2
        )
        self.assertIn(
            new_post,
            new_posts
        )

    def test_new_author_post_for_unfollower(self):
        """Новая запись в ленте не подписанных пользователей."""
        client = self.authorized_user_unfollow_client
        author = self.author
        group = self.group
        response_old = client.get(
            reverse('posts:follow_index')
        )
        old_posts = response_old.context.get(
            'page_obj'
        ).object_list
        self.assertEqual(
            len(response_old.context.get('page_obj').object_list),
            0
        )
        self.assertNotIn(
            self.post,
            old_posts
        )
        new_post = Post.objects.create(
            text='test_new_post',
            group=group,
            author=author
        )
        cache.clear()
        response_new = client.get(
            reverse('posts:follow_index')
        )
        new_posts = response_new.context.get(
            'page_obj'
        ).object_list
        self.assertEqual(
            len(response_new.context.get('page_obj').object_list),
            0
        )
        self.assertNotIn(
            new_post,
            new_posts
        )
