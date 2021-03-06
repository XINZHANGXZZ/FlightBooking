# Generated by Django 2.0.3 on 2018-03-29 21:06

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('polls', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='FlightOccupiedSeat',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(verbose_name='Flight_date')),
                ('occupied_seat', models.IntegerField(verbose_name='Occupied_seat')),
                ('fid', models.ForeignKey(db_column='FID', on_delete=django.db.models.deletion.DO_NOTHING, to='polls.Flight')),
            ],
        ),
    ]
