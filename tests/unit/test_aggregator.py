from src.pipeline.aggregator import MetricsAggregator

def test_aggregator_override():
    agg = MetricsAggregator()
    builtin = [{"name": "cpu.usage", "value": 1, "type": "numeric"}]
    vendor  = [{"name": "cpu.usage", "value": 2, "type": "numeric"}]

    merged = agg.aggregate(builtin, vendor)
    assert merged[0]["value"] == 2
