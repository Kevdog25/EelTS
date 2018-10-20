from eel import eel

@eel.expose
def function():
    print('Function working')

e = eel('Web')

e.start('page.html')