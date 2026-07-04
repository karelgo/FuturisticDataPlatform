{{- define "carina.fullname" -}}
{{- printf "%s" .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "carina.labels" -}}
app.kubernetes.io/name: carina
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "carina.selectorLabels" -}}
app.kubernetes.io/name: carina
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
