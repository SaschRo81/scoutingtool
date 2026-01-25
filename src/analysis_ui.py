{% extends "layout.html" %}

{% block content %}
<div class="card">
    <h1>💸 Finanz-Journal</h1>
    
    <!-- KPI Header wie gehabt -->
    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-bottom: 20px;">
        <div class="card" style="border-left: 5px solid #28a745;">
            <small>Einnahmen</small><br><strong>{{ "%.2f"|format(total_einnahmen) }} €</strong>
        </div>
        <div class="card" style="border-left: 5px solid #dc3545;">
            <small>Ausgaben</small><br><strong>{{ "%.2f"|format(total_ausgaben) }} €</strong>
        </div>
        <div class="card" style="border-left: 5px solid #333;">
            <small>Bilanz</small><br><strong>{{ "%.2f"|format(bilanz) }} €</strong>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th>Datum</th>
                <th>Vorgang</th>
                <th>Quelle</th>
                <th style="text-align:right;">Betrag</th>
                <th style="text-align:right;">Aktion</th>
            </tr>
        </thead>
        <tbody>
            {% for t in transaktionen %}
            <tr style="{% if t.storniert %}opacity: 0.4; text-decoration: line-through; background: #f9f9f9;{% endif %}">
                <td>{{ t.datum.strftime('%d.%m.%Y') }}</td>
                <td>
                    <strong>{{ t.titel }}</strong><br>
                    <small>{{ t.kategorie }}</small>
                </td>
                <td><a href="{{ t.link }}">{{ t.quelle }}</a></td>
                <td style="text-align:right; font-weight:bold; color: {% if t.typ == 'Einnahme' %}green{% else %}red{% endif %};">
                    {% if t.typ == 'Ausgabe' %}-{% endif %}{{ "%.2f"|format(t.betrag) }} €
                </td>
                <td style="text-align:right;">
                    {% if not t.storniert %}
                        <a href="{{ url_for('rechnung.storno', model_name=t.db_model, id=t.id) }}" 
                           class="btn btn-small" style="background:#666;"
                           onclick="return confirm('Buchung stornieren? Löschen ist nicht möglich.')">Storno</a>
                    {% else %}
                        <small>STORNIERT</small>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
