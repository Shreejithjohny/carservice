from django.core.management.base import BaseCommand, CommandError

from api.ml_cost_model import MIN_TRAINING_SAMPLES, train_cost_model


class Command(BaseCommand):
    help = "Trains the repair-cost model on completed, approved repairs and makes it the active estimator."

    def add_arguments(self, parser):
        parser.add_argument("--min-samples", type=int, default=MIN_TRAINING_SAMPLES)

    def handle(self, *args, **options):
        try:
            model = train_cost_model(min_samples=options["min_samples"])
        except ValueError as exc:
            raise CommandError(str(exc))
        m = model.metrics
        self.stdout.write(f"Trained on {model.n_samples} repairs ({model.synthetic_share}% synthetic).")
        self.stdout.write(f"  Learned model   MAE Rs.{m['ml']['mae']:,.0f}  MAPE {m['ml']['mape']}%")
        self.stdout.write(f"  Rule formula    MAE Rs.{m['rule_based']['mae']:,.0f}  MAPE {m['rule_based']['mape']}%")
        self.stdout.write(f"  80% range coverage on held-out repairs: {m['interval_coverage']}%")
        if model.synthetic_share:
            self.stdout.write(self.style.WARNING("Synthetic data present: these numbers describe the generator, not real workshops."))
