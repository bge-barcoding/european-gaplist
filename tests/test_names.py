import pytest

from gaplist.names import parse


@pytest.mark.parametrize(
    "raw, canonical, uncertain",
    [
        ("Aagaardia protensa", "Aagaardia protensa", False),
        ("  Aagaardia   protensa ", "Aagaardia protensa", False),
        ("Chironomus (Camptochironomus) tentans", "Chironomus tentans", False),
        ("Chersotis multangula andreae", "Chersotis multangula andreae", False),
        ("Melanotus villosus var. aspericollis", "Melanotus villosus aspericollis", False),
        ("Luffia lapidella f. ferchaultella (parth. Form)", "Luffia lapidella ferchaultella", False),
        ("Culex pipiens s.l.", "Culex pipiens", False),
        ("Anopheles maculipennis sl.", "Anopheles maculipennis", False),
        ("Aleiodes gastritor agg", "Aleiodes gastritor", False),
        ("Aleiodes gastritor group", "Aleiodes gastritor", False),
        ("Hoplodrina superstes?", "Hoplodrina superstes", False),
        ("Praebursoplana steinböcki", "Praebursoplana steinbocki", False),
        ("Cryptocephalus cfr. eridani", "Cryptocephalus eridani", True),
        ("Chrysolina cfr haemoptera", "Chrysolina haemoptera", True),
        ("Mycetophila biformis PJ hom", "Mycetophila biformis", False),
    ],
)
def test_species_names(raw, canonical, uncertain):
    parsed = parse(raw)
    assert parsed.canonical == canonical
    assert parsed.uncertain is uncertain


@pytest.mark.parametrize(
    "raw, reason",
    [
        ("Arion ater x Arion rufus", "hybrid"),
        ("Schrankia costaestrigalis x taenialis", "hybrid"),
        ("Lebertia porosa aggr. sp. BOLD:ACS0974", "placeholder (BOLD BIN)"),
        ("Lebertia porosa aggr. sp. A", "unnamed species (sp.)"),
        ("Cymodusa AH3", "placeholder, not a species epithet"),
        ("Cotesia jft56", "placeholder, not a species epithet"),
        ("Trifurcula aurellaGreece", "placeholder, not a species epithet"),
        ("Campylaspis var.", "no species epithet"),
        ("Sciocoris (Sciocoris) ", "genus only"),
    ],
)
def test_not_species(raw, reason):
    parsed = parse(raw)
    assert parsed.canonical is None
    assert reason in parsed.notes


def test_binomial_of_trinomial():
    assert parse("Chersotis multangula andreae").binomial == "Chersotis multangula"
