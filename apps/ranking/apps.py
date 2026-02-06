from django.apps import AppConfig


class RankingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ranking'

    def ready(self):
        import apps.ranking.signals
