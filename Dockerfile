
FROM python:3.9-slim 



ENV PYTHONDONTWRITEBYTECODE 1 
ENV PYTHONUNBUFFERED 1    

# Set work directory
WORKDIR /app


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project code into the container
COPY . .

# Run collectstatic (as done in your build.sh)
# Ensure DJANGO_SETTINGS_MODULE is set if needed, or manage settings via environment variables
RUN python manage.py collectstatic --no-input --settings=spotterAi.settings

# Expose the port the app runs on (Gunicorn default is often 8000)
EXPOSE 8000


CMD ["gunicorn", "spotterAi.wsgi:application", "--bind", "0.0.0.0:8000"]