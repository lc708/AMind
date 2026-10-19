import html
def render(text):
    return '<article>'+html.escape(text,quote=True)+'</article>'
