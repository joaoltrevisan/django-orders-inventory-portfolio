from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from olist.benchmark import run_experiment


class Command(BaseCommand):
    help = "Measure a temporary candidate index only on the isolated historical benchmark database."

    def add_arguments(self, parser):
        parser.add_argument("--expected-database", required=True)
        parser.add_argument("--output", type=Path, required=True)

    def handle(self, *args, **options):
        try:
            report = run_experiment(
                expected_database=options["expected_database"], output=options["output"]
            )
        except Exception as error:
            raise CommandError(
                "Benchmark failed or refused; inspect retained evidence. "
                "No automatic data reset is performed."
            ) from error
        self.stdout.write(
            f"Measured baseline/index/control with {report['measured_runs_per_phase']} runs each; "
            "plans, medians and index bytes retained."
        )
