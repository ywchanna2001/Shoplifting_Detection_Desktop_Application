from shopguard.core.incidents import Sample, group_incidents


def make_samples(scores, fps=5.0):
    return [Sample(time=i / fps, score=s) for i, s in enumerate(scores)]


def test_no_incident_when_nothing_suspicious():
    assert group_incidents(make_samples([0.1] * 50), threshold=0.45) == []


def test_single_noisy_frame_is_ignored():
    scores = [0.0] * 20 + [0.9] + [0.0] * 20
    assert group_incidents(make_samples(scores), threshold=0.45, min_hits=3) == []


def test_consecutive_frames_form_one_incident():
    scores = [0.0] * 10 + [0.6, 0.8, 0.7, 0.9] + [0.0] * 10
    incidents = group_incidents(make_samples(scores), threshold=0.45, min_hits=3, padding=1.0)
    assert len(incidents) == 1
    incident = incidents[0]
    assert incident.hits == 4
    assert incident.peak_confidence == 0.9
    assert incident.start == 10 / 5 - 1.0
    assert incident.end == 13 / 5 + 1.0


def test_short_gap_is_merged_long_gap_is_split():
    scores = [0.8] * 3 + [0.0] * 5 + [0.8] * 3 + [0.0] * 30 + [0.8] * 3
    incidents = group_incidents(make_samples(scores), threshold=0.45, min_hits=3, max_gap=2.0)
    assert len(incidents) == 2
    assert incidents[0].hits == 6
    assert [i.id for i in incidents] == [1, 2]


def test_padding_stays_inside_video():
    incidents = group_incidents(
        make_samples([0.9] * 5), threshold=0.45, min_hits=3, padding=5.0, video_duration=1.0
    )
    assert incidents[0].start == 0.0
    assert incidents[0].end == 1.0
