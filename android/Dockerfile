FROM mobiledevops/android-sdk-image:36.1.0
WORKDIR /app
COPY android /app/android
RUN /app/android/build.sh
CMD ["bash", "-lc", "/app/android/build.sh && cd /app/build/android && python3 -m http.server ${PORT:-8080}"]
