---
layout: page
title: Episodes
---

<ul>
  {% for post in site.posts %}
    <li>
      <b><a href="{{ post.url }}">{{ post.title }}</a></b>
      {% if post.subtitle  %}
      <ul>
        <li><b>{{ post.subtitle }}</b></li>
      </ul>
      {% endif %}
    </li>
  {% endfor %}
</ul>
