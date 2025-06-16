from django.db import models

class League(models.Model):
    name = models.CharField(max_length=100)
    country = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} ({self.country})"

class Club(models.Model):
    name = models.CharField(max_length=100)
    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name='clubs')
    founded_year = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.name

class Player(models.Model):
    fotmob_id = models.IntegerField(unique=True, null=True, blank=True)
    name = models.CharField(max_length=100)
    club = models.ForeignKey('Club', on_delete=models.CASCADE, related_name='players', null=True, blank=True)
    position = models.CharField(max_length=50)
    country = models.CharField(max_length=50)
    shirt_number = models.IntegerField(null=True, blank=True)
    age = models.IntegerField(null=True, blank=True)
    height = models.CharField(max_length=10, null=True, blank=True)
    market_value = models.BigIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.club.name})"

class Data(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='data')

    # Shooting
    goals = models.IntegerField(null=True, blank=True)
    expected_goals = models.FloatField(null=True, blank=True)
    xg_on_target = models.FloatField(null=True, blank=True)
    penalty_goals = models.IntegerField(null=True, blank=True)
    non_penalty_xg = models.FloatField(null=True, blank=True)
    shots = models.IntegerField(null=True, blank=True)
    shots_on_target = models.IntegerField(null=True, blank=True)

    # Passing
    assists = models.IntegerField(null=True, blank=True)
    expected_assists = models.FloatField(null=True, blank=True)
    successful_passes = models.FloatField(null=True, blank=True)
    pass_accuracy = models.FloatField(null=True, blank=True)
    accurate_long_balls = models.IntegerField(null=True, blank=True)
    long_ball_accuracy = models.FloatField(null=True, blank=True)
    chances_created = models.IntegerField(null=True, blank=True)
    successful_crosses = models.IntegerField(null=True, blank=True)
    cross_accuracy = models.FloatField(null=True, blank=True)

    # Possession
    successful_dribbles = models.IntegerField(null=True, blank=True)
    dribble_success = models.FloatField(null=True, blank=True)
    touches = models.FloatField(null=True, blank=True)
    touches_in_opposition_box = models.IntegerField(null=True, blank=True)
    dispossessed = models.IntegerField(null=True, blank=True)
    fouls_won = models.IntegerField(null=True, blank=True)
    penalties_awarded = models.IntegerField(null=True, blank=True)

    # Defending
    tackles_won = models.IntegerField(null=True, blank=True)
    tackles_won_percentage = models.FloatField(null=True, blank=True)
    duels_won = models.IntegerField(null=True, blank=True)
    duels_won_percentage = models.FloatField(null=True, blank=True)
    aerial_duels_won = models.IntegerField(null=True, blank=True)
    aerial_duels_won_percentage = models.FloatField(null=True, blank=True)
    interceptions = models.IntegerField(null=True, blank=True)
    blocked = models.IntegerField(null=True, blank=True)
    fouls_committed = models.IntegerField(null=True, blank=True)
    recoveries = models.IntegerField(null=True, blank=True)
    possession_won_final_3rd = models.IntegerField(null=True, blank=True)
    dribbled_past = models.IntegerField(null=True, blank=True)

    # Discipline
    yellow_cards = models.IntegerField(null=True, blank=True)
    red_cards = models.IntegerField(null=True, blank=True)

    # Goalkeeping
    saves = models.IntegerField(null=True, blank=True)
    save_percentage = models.FloatField(null=True, blank=True)
    goals_conceded = models.IntegerField(null=True, blank=True)
    goals_prevented = models.FloatField(null=True, blank=True)
    clean_sheets = models.IntegerField(null=True, blank=True)
    error_led_to_goal = models.IntegerField(null=True, blank=True)
    high_claim = models.IntegerField(null=True, blank=True)

    # Goalkeeping Distribution
    gk_pass_accuracy = models.FloatField(null=True, blank=True)
    gk_accurate_long_balls = models.IntegerField(null=True, blank=True)
    gk_long_ball_accuracy = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"Data for {self.player.name}"
    