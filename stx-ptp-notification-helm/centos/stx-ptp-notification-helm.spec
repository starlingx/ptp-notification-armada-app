#
# Copyright (c) 2021-2022 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
# Application tunables (maps to metadata)
%global app_name ptp-notification
%global helm_repo stx-platform

# Install location
%global app_folder /usr/local/share/applications/helm

# Build variables
%global helm_folder /usr/lib/helm

Summary: StarlingX PTP Notification FluxCD Helm Charts
Name: stx-ptp-notification-helm
Version: 1.0
Release: %{tis_patch_ver}%{?_tis_dist}
License: Apache-2.0
Group: base
Packager: Wind River <info@windriver.com>
URL: unknown

Source0: %{name}-%{version}.tar.gz

BuildArch: noarch

BuildRequires: helm
BuildRequires: chartmuseum
BuildRequires: python-k8sapp-ptp-notification
BuildRequires: python-k8sapp-ptp-notification-wheels

%description
StarlingX PTP Notification FluxCD Helm Charts

%prep
%setup -n %{name}-%{version}

%build
chartmuseum --debug --port=8879 --context-path='/charts' --storage="local" --storage-local-rootdir="." &
sleep 2

helm repo add local http://localhost:8879/charts

cd helm-charts
make ptp-notification
make psp-rolebinding
cd -

# Terminate helm server (the last backgrounded task)
kill %1

# Create a chart tarball compliant with sysinv kube-app.py
%define app_staging %{_builddir}/staging
%define app_tarball_fluxcd %{app_name}-%{version}-%{tis_patch_ver}.tgz
%define fluxcd_app_path %{_builddir}/%{app_tarball_fluxcd}

# Setup staging
mkdir -p %{app_staging}
cp files/metadata.yaml %{app_staging}
mkdir -p %{app_staging}/charts
cp helm-charts/*.tgz %{app_staging}/charts

# Populate metadata
sed -i 's/@APP_NAME@/%{app_name}/g' %{app_staging}/metadata.yaml
sed -i 's/@APP_VERSION@/%{version}-%{tis_patch_ver}/g' %{app_staging}/metadata.yaml
sed -i 's/@HELM_REPO@/%{helm_repo}/g' %{app_staging}/metadata.yaml

# Copy the plugins: installed in the buildroot
mkdir -p %{app_staging}/plugins
cp /plugins/%{app_name}/*.whl %{app_staging}/plugins

# package fluxcd
cp -R fluxcd-manifests %{app_staging}/

# calculate checksum of all files in app_staging
cd %{app_staging}
find . -type f ! -name '*.md5' -print0 | xargs -0 md5sum > checksum.md5
tar -zcf %fluxcd_app_path -C %{app_staging}/ .

cd -

# Cleanup staging
rm -fr %{app_staging}

%install
install -d -m 755 %{buildroot}/%{app_folder}
install -p -D -m 755 %fluxcd_app_path %{buildroot}/%{app_folder}

%files
%defattr(-,root,root,-)
%{app_folder}/%{app_tarball_fluxcd}
