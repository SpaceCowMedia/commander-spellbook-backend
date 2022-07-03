from django.db.models.signals import m2m_changed, post_delete
from django.dispatch import receiver
from .models import Card, Feature, Combo, Variant
from django.db import transaction
from sympy import Symbol, And, Xor, S, satisfiable

def get_expression_from_combo(combo: Combo) -> And:
  expression = []
  for card in combo.includes.all():
    expression.append(Symbol(name=str(card.id)))
  for effect in combo.needs.all():
    expression.append(get_expression_from_effect(effect))
  if len(expression) == 0:
      return S.true
  elif len(expression) == 1:
    return expression[0]
  return And(*expression)

def get_expression_from_effect(effect: Feature)-> Xor:
  expression = []
  for card in Card.objects.filter(features=effect):
    expression.append(Symbol(name=str(card.id)))
  for combo in Combo.objects.filter(produces=effect):
    expression.append(get_expression_from_combo(combo))
  if len(expression) == 0:
    return S.false
  if len(expression) == 1:
    return expression[0]
  return Xor(*expression)

def get_cards_for_combo(combo: Combo) -> list[list[Card]]:
  result = []
  for model in satisfiable(get_expression_from_combo(combo), all_models=True):
    if model is False:
        raise Exception(f'Combo {combo.id} is not satisfiable: {str(combo)}')
    result.append([Card.objects.get(pk=symbol.name) for symbol in model if model[symbol]])
  return result

def create_variant(combo: Combo, cards: list[Card]):
  variant = Variant(of=combo, status=Variant.Status.DRAFT)
  variant.save()
  variant.includes.set(cards)
  variant.produces.set(combo.produces.all())
  variant.save()

def update_variants():
    with transaction.atomic():
            print('Updating variants...')
            Variant.objects.all().delete()
            for combo in Combo.objects.all():
                cards = get_cards_for_combo(combo)
                for card_list in cards:
                    create_variant(combo, card_list)
            print('Done.')

@receiver(m2m_changed, sender=Card)
@receiver(m2m_changed, sender=Feature)
@receiver(m2m_changed, sender=Combo)
def on_many_to_many_update(sender, instance, action, reverse, model, **kwargs):
    if action in ['post_add', 'post_remove', 'post_clear']:
        update_variants()

@receiver(post_delete, sender=Card)
@receiver(post_delete, sender=Feature)
@receiver(post_delete, sender=Combo)
def on_delete(sender, instance, **kwargs):
    update_variants()
