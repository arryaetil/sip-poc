"""Chat-driven context selection, safe ambiguity, and website supplement provenance."""
import json
from types import SimpleNamespace
import pytest
from app import main
from app.context_intent import resolve_intent
from app.models import ProductStrategistTurn
from app.knowledge import KnowledgeDocument
from test_context_versions import env, signed_in, approved

class Router:
    def __init__(self, result): self.result=result
    def strategist_turn(self,*args):return ProductStrategistTurn(message=json.dumps(self.result),is_ready_to_save=False,readiness_reason='')

@pytest.mark.parametrize('result', [
    {'action':'update','target_id':'not-accessible'},
    {'action':'website','target_id':'invented'},
    {'action':'clarify','question':''},
])
def test_untrusted_route_cannot_select_unknown_sources(result):
    conversation=SimpleNamespace(messages=[],language='nl',created_at='now')
    assert resolve_intent(Router(result),conversation,'bijwerken','alice',[],[],True).action=='clarify'


def test_chat_selects_update_and_retains_existing_review_flow(env, monkeypatch):
    store,assistant=env;target=approved(store)
    original=assistant.strategist_turn
    def turn(history,message,language,owner_id,extra=''):
        if 'First resolve' in extra:
            return Router({'action':'update','target_id':target}).strategist_turn()
        return original(history,message,language,owner_id,extra)
    monkeypatch.setattr(assistant,'strategist_turn',turn)
    http=signed_in('po@test.nl','po-pass');conversation=http.post('/api/conversations',json={'language':'nl'}).json()
    response=http.post(f"/api/conversations/{conversation['id']}/messages",json={'message':'Werk WoonAtlas bij voor woningcorporaties'})
    assert response.status_code==200
    assert response.json()['conversation']['updates_context_id']==target
    assert len(store.list_context_versions(target))==1
    assert http.post(f"/api/conversations/{conversation['id']}/portfolio").status_code==409
    assert http.post(f"/api/conversations/{conversation['id']}/update-proposal").status_code==200


def test_ambiguity_stays_in_chat_without_ready_or_write(env, monkeypatch):
    store,assistant=env
    monkeypatch.setattr(assistant,'strategist_turn',Router({'action':'clarify','question':'Welke websitepagina bedoel je?'}).strategist_turn)
    http=signed_in('po@test.nl','po-pass');c=http.post('/api/conversations').json()
    response=http.post(f"/api/conversations/{c['id']}/messages",json={'message':'Vul die website aan'}).json()
    assert response['assistant_message']['content']=='Welke websitepagina bedoel je?'
    assert response['conversation']['context_intent']=='pending'
    assert http.post(f"/api/conversations/{c['id']}/portfolio").status_code==409


def test_website_baseline_survives_reload_and_finalization(env, monkeypatch):
    store,assistant=env
    document=KnowledgeDocument('website-1','Smart Service Center','https://example.test/sam','ibc','nl','service','Originele website-inhoud')
    monkeypatch.setattr(main,'load_knowledge_documents',lambda:[document]);monkeypatch.setattr(main,'get_knowledge_document',lambda identifier:document if identifier==document.source_id else None)
    original=assistant.strategist_turn
    def turn(history,message,language,owner_id,extra=''):
        if 'First resolve' in extra:return Router({'action':'website','target_id':document.source_id}).strategist_turn()
        return original(history,message,language,owner_id,extra)
    monkeypatch.setattr(assistant,'strategist_turn',turn)
    http=signed_in('po@test.nl','po-pass');c=http.post('/api/conversations').json()
    response=http.post(f"/api/conversations/{c['id']}/messages",json={'message':'Vul Smart Service Center aan met onze nieuwe dienstverlening'}).json()
    assert response['conversation']['website_source_id']==document.source_id
    http.post(f"/api/conversations/{c['id']}/messages",json={'message':'Ook voor dealerbedrijven'})
    assert document.canonical_url in assistant.strategist_calls[-1]['history'][0].content
    assert http.post(f"/api/conversations/{c['id']}/portfolio").status_code==201
    assert document.content in assistant.prepared[-1][0].content
    assert document.canonical_url in assistant.prepared[-1][0].content
    assert http.get(f"/api/conversations/{c['id']}").json()['website_source_id']==document.source_id


def test_routing_cannot_grant_update_permission():
    conversation = SimpleNamespace(messages=[], language='nl', created_at='now')
    context = SimpleNamespace(id='approved', name='SAM')
    result = resolve_intent(Router({'action':'update', 'target_id':'approved'}),
                            conversation, 'werk SAM bij', 'alice', [context], [], False)
    assert result.action == 'clarify'
